using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace WasapiRawMeter
{
    internal static class Program
    {
        private static volatile bool running = true;
        private static readonly Guid IidAudioClient2 = new Guid("726778CD-F60A-4eda-82DE-E47610CD78AA");
        private static readonly Guid IidAudioCaptureClient = new Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317");
        private static readonly PropertyKey FriendlyNameKey = new PropertyKey(
            new Guid("A45C254E-DF1C-4EFD-8020-67D146A850E0"), 14);
        private static readonly Guid PcmSubformat = new Guid("00000001-0000-0010-8000-00AA00389B71");
        private static readonly Guid FloatSubformat = new Guid("00000003-0000-0010-8000-00AA00389B71");

        public static int Main(string[] args)
        {
            string needle = "Wireless Mic Rx";
            bool pcmMode = false;
            for (int index = 0; index < args.Length - 1; index++)
            {
                if (args[index] == "--device") needle = args[index + 1];
            }
            for (int index = 0; index < args.Length; index++)
            {
                if (args[index] == "--pcm") pcmMode = true;
            }

            Console.CancelKeyPress += delegate(object sender, ConsoleCancelEventArgs eventArgs)
            {
                eventArgs.Cancel = true;
                running = false;
            };

            try
            {
                RunCapture(needle, pcmMode);
                return 0;
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine(exception.ToString());
                return 1;
            }
        }

        private static void RunCapture(string needle, bool pcmMode)
        {
            IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
            IMMDeviceCollection collection;
            Check(enumerator.EnumAudioEndpoints(EDataFlow.Capture, DeviceState.Active, out collection), "EnumAudioEndpoints");
            uint count;
            Check(collection.GetCount(out count), "GetCount");

            IMMDevice selected = null;
            string selectedName = null;
            for (uint index = 0; index < count; index++)
            {
                IMMDevice device;
                Check(collection.Item(index, out device), "Item");
                string name = GetFriendlyName(device);
                if (name != null && name.IndexOf(needle, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    selected = device;
                    selectedName = name;
                    break;
                }
                Marshal.ReleaseComObject(device);
            }
            if (selected == null) throw new InvalidOperationException("DJI-ontvanger niet gevonden: " + needle);

            object activated;
            Guid clientId = IidAudioClient2;
            Check(selected.Activate(ref clientId, ClsCtx.All, IntPtr.Zero, out activated), "Activate IAudioClient2");
            IAudioClient2 client = (IAudioClient2)activated;

            AudioClientProperties properties = new AudioClientProperties();
            properties.Size = (uint)Marshal.SizeOf(typeof(AudioClientProperties));
            properties.IsOffload = 0;
            properties.Category = AudioStreamCategory.Other;
            properties.Options = AudioClientStreamOptions.Raw;
            Check(client.SetClientProperties(ref properties), "SetClientProperties(RAW)");

            IntPtr formatPointer;
            Check(client.GetMixFormat(out formatPointer), "GetMixFormat");
            WaveFormat format = WaveFormat.Read(formatPointer);
            if (format.Channels < 1) throw new InvalidOperationException("Het audioformaat bevat geen kanalen.");

            Guid session = Guid.Empty;
            Check(
                client.Initialize(
                    AudioClientShareMode.Shared,
                    AudioClientStreamFlags.NoPersist,
                    1000000,
                    0,
                    formatPointer,
                    ref session),
                "Initialize RAW stream");

            object captureObject;
            Guid captureId = IidAudioCaptureClient;
            Check(client.GetService(ref captureId, out captureObject), "GetService(IAudioCaptureClient)");
            IAudioCaptureClient capture = (IAudioCaptureClient)captureObject;

            Check(client.Start(), "Start");
            Console.Error.WriteLine(
                "RAW WASAPI: " + selectedName + ", " + format.Channels + " kanalen, " +
                format.SampleRate + " Hz, " + format.BitsPerSample + " bit");

            MeterAccumulator meter = pcmMode
                ? null
                : new MeterAccumulator(format.Channels, Math.Max(1, format.SampleRate / 10));
            Stream pcmOutput = null;
            if (pcmMode)
            {
                pcmOutput = Console.OpenStandardOutput();
                byte[] magic = Encoding.ASCII.GetBytes("DJIRAW1\0");
                pcmOutput.Write(magic, 0, magic.Length);
                byte[] channelBytes = BitConverter.GetBytes(format.Channels);
                pcmOutput.Write(channelBytes, 0, channelBytes.Length);
                byte[] rateBytes = BitConverter.GetBytes(format.SampleRate);
                pcmOutput.Write(rateBytes, 0, rateBytes.Length);
                pcmOutput.Flush();
            }
            try
            {
                while (running)
                {
                    uint packetFrames;
                    Check(capture.GetNextPacketSize(out packetFrames), "GetNextPacketSize");
                    if (packetFrames == 0)
                    {
                        Thread.Sleep(2);
                        continue;
                    }

                    while (packetFrames > 0)
                    {
                        IntPtr data;
                        uint frames;
                        AudioClientBufferFlags flags;
                        ulong devicePosition;
                        ulong qpcPosition;
                        Check(
                            capture.GetBuffer(out data, out frames, out flags, out devicePosition, out qpcPosition),
                            "GetBuffer");
                        try
                        {
                            if (pcmMode)
                            {
                                WritePcm(pcmOutput, data, frames, flags, format);
                            }
                            else
                            {
                                meter.Add(data, frames, flags, format);
                                if (meter.Ready)
                                {
                                    Console.WriteLine(meter.ToJson(selectedName, format));
                                    Console.Out.Flush();
                                    meter.Reset();
                                }
                            }
                        }
                        finally
                        {
                            Check(capture.ReleaseBuffer(frames), "ReleaseBuffer");
                        }
                        Check(capture.GetNextPacketSize(out packetFrames), "GetNextPacketSize");
                    }
                }
            }
            finally
            {
                client.Stop();
                Marshal.FreeCoTaskMem(formatPointer);
                Marshal.ReleaseComObject(capture);
                Marshal.ReleaseComObject(client);
                Marshal.ReleaseComObject(selected);
                Marshal.ReleaseComObject(collection);
                Marshal.ReleaseComObject(enumerator);
            }
        }

        private static void WritePcm(
            Stream output,
            IntPtr data,
            uint frameCount,
            AudioClientBufferFlags flags,
            WaveFormat format)
        {
            int sampleCount = checked((int)frameCount * format.Channels);
            double[] source = new double[sampleCount];
            if ((flags & AudioClientBufferFlags.Silent) == 0)
            {
                format.CopySamples(data, source);
            }
            float[] samples = new float[sampleCount];
            for (int index = 0; index < sampleCount; index++)
            {
                samples[index] = (float)Math.Max(-1.0, Math.Min(1.0, source[index]));
            }
            byte[] bytes = new byte[samples.Length * sizeof(float)];
            Buffer.BlockCopy(samples, 0, bytes, 0, bytes.Length);
            output.Write(bytes, 0, bytes.Length);
            output.Flush();
        }

        private static string GetFriendlyName(IMMDevice device)
        {
            IPropertyStore store;
            Check(device.OpenPropertyStore(StorageAccessMode.Read, out store), "OpenPropertyStore");
            PropVariant value;
            PropertyKey key = FriendlyNameKey;
            Check(store.GetValue(ref key, out value), "GetValue(FriendlyName)");
            string result = value.AsString();
            value.Clear();
            if (store != null && Marshal.IsComObject(store)) Marshal.ReleaseComObject(store);
            return result;
        }

        private static void Check(int result, string operation)
        {
            if (result < 0) Marshal.ThrowExceptionForHR(result, new IntPtr(-1));
        }

        private sealed class MeterAccumulator
        {
            private readonly int channels;
            private readonly long targetFrames;
            private readonly double[] sums;
            private readonly double[] squareSums;
            private readonly double[] peaks;
            private readonly double[,] crossSums;
            private long frames;

            public MeterAccumulator(int channels, long targetFrames)
            {
                this.channels = channels;
                this.targetFrames = targetFrames;
                sums = new double[channels];
                squareSums = new double[channels];
                peaks = new double[channels];
                crossSums = new double[channels, channels];
            }

            public bool Ready { get { return frames >= targetFrames; } }

            public void Add(IntPtr data, uint frameCount, AudioClientBufferFlags flags, WaveFormat format)
            {
                int sampleCount = checked((int)frameCount * channels);
                double[] samples = new double[sampleCount];
                if ((flags & AudioClientBufferFlags.Silent) == 0)
                {
                    format.CopySamples(data, samples);
                }

                for (int frame = 0; frame < frameCount; frame++)
                {
                    int offset = frame * channels;
                    for (int channel = 0; channel < channels; channel++)
                    {
                        double sample = samples[offset + channel];
                        sums[channel] += sample;
                        squareSums[channel] += sample * sample;
                        peaks[channel] = Math.Max(peaks[channel], Math.Abs(sample));
                    }
                    for (int left = 0; left < channels; left++)
                    {
                        for (int right = left + 1; right < channels; right++)
                        {
                            crossSums[left, right] += samples[offset + left] * samples[offset + right];
                        }
                    }
                }
                frames += frameCount;
            }

            public string ToJson(string deviceName, WaveFormat format)
            {
                StringBuilder json = new StringBuilder();
                json.Append("{\"ok\":true,\"raw\":true,\"device\":\"");
                json.Append(Escape(deviceName));
                json.Append("\",\"channels\":").Append(channels);
                json.Append(",\"sample_rate\":").Append(format.SampleRate);
                json.Append(",\"levels\":[");
                for (int channel = 0; channel < channels; channel++)
                {
                    if (channel > 0) json.Append(',');
                    double rms = Math.Sqrt(squareSums[channel] / Math.Max(1, frames));
                    double db = 20.0 * Math.Log10(Math.Max(rms, 0.00000001));
                    json.Append("{\"rms\":").Append(Number(rms));
                    json.Append(",\"dbfs\":").Append(Number(db));
                    json.Append(",\"peak\":").Append(Number(peaks[channel])).Append('}');
                }
                json.Append("],\"correlations\":[");
                bool first = true;
                for (int left = 0; left < channels; left++)
                {
                    for (int right = left + 1; right < channels; right++)
                    {
                        if (!first) json.Append(',');
                        first = false;
                        double count = Math.Max(1, frames);
                        double covariance = crossSums[left, right] - sums[left] * sums[right] / count;
                        double varianceLeft = squareSums[left] - sums[left] * sums[left] / count;
                        double varianceRight = squareSums[right] - sums[right] * sums[right] / count;
                        double denominator = Math.Sqrt(Math.Max(0, varianceLeft * varianceRight));
                        double value = denominator > 0.000000000001 ? covariance / denominator : 0;
                        json.Append("{\"left\":").Append(left + 1);
                        json.Append(",\"right\":").Append(right + 1);
                        json.Append(",\"value\":").Append(Number(value)).Append('}');
                    }
                }
                json.Append("]}");
                return json.ToString();
            }

            public void Reset()
            {
                frames = 0;
                Array.Clear(sums, 0, sums.Length);
                Array.Clear(squareSums, 0, squareSums.Length);
                Array.Clear(peaks, 0, peaks.Length);
                Array.Clear(crossSums, 0, crossSums.Length);
            }

            private static string Number(double value)
            {
                return value.ToString("0.########", CultureInfo.InvariantCulture);
            }

            private static string Escape(string value)
            {
                return (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");
            }
        }

        private sealed class WaveFormat
        {
            public ushort FormatTag;
            public int Channels;
            public int SampleRate;
            public int BlockAlign;
            public int BitsPerSample;
            public Guid Subformat;

            public static WaveFormat Read(IntPtr pointer)
            {
                WaveFormat result = new WaveFormat();
                result.FormatTag = unchecked((ushort)Marshal.ReadInt16(pointer, 0));
                result.Channels = unchecked((ushort)Marshal.ReadInt16(pointer, 2));
                result.SampleRate = Marshal.ReadInt32(pointer, 4);
                result.BlockAlign = unchecked((ushort)Marshal.ReadInt16(pointer, 12));
                result.BitsPerSample = unchecked((ushort)Marshal.ReadInt16(pointer, 14));
                result.Subformat = result.FormatTag == 0xFFFE
                    ? (Guid)Marshal.PtrToStructure(IntPtr.Add(pointer, 24), typeof(Guid))
                    : result.FormatTag == 3 ? FloatSubformat : PcmSubformat;
                return result;
            }

            public void CopySamples(IntPtr pointer, double[] destination)
            {
                if (Subformat == FloatSubformat && BitsPerSample == 32)
                {
                    float[] values = new float[destination.Length];
                    Marshal.Copy(pointer, values, 0, values.Length);
                    for (int index = 0; index < values.Length; index++) destination[index] = values[index];
                    return;
                }

                int bytesPerSample = BitsPerSample / 8;
                byte[] bytes = new byte[destination.Length * bytesPerSample];
                Marshal.Copy(pointer, bytes, 0, bytes.Length);
                for (int index = 0; index < destination.Length; index++)
                {
                    int offset = index * bytesPerSample;
                    if (bytesPerSample == 2)
                    {
                        short value = (short)(bytes[offset] | (bytes[offset + 1] << 8));
                        destination[index] = value / 32768.0;
                    }
                    else if (bytesPerSample == 3)
                    {
                        int value = bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16);
                        if ((value & 0x800000) != 0) value |= unchecked((int)0xFF000000);
                        destination[index] = value / 8388608.0;
                    }
                    else if (bytesPerSample == 4)
                    {
                        int value = BitConverter.ToInt32(bytes, offset);
                        destination[index] = value / 2147483648.0;
                    }
                    else
                    {
                        throw new NotSupportedException("Niet-ondersteunde bitdiepte: " + BitsPerSample);
                    }
                }
            }
        }

        [DllImport("ole32.dll")]
        private static extern int PropVariantClear(ref PropVariant variant);

        [StructLayout(LayoutKind.Sequential)]
        private struct PropertyKey
        {
            public Guid FormatId;
            public uint PropertyId;
            public PropertyKey(Guid formatId, uint propertyId) { FormatId = formatId; PropertyId = propertyId; }
        }

        [StructLayout(LayoutKind.Explicit)]
        private struct PropVariant
        {
            [FieldOffset(0)] public ushort VariantType;
            [FieldOffset(8)] public IntPtr PointerValue;
            public string AsString() { return VariantType == 31 ? Marshal.PtrToStringUni(PointerValue) : null; }
            public void Clear() { PropVariantClear(ref this); }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct AudioClientProperties
        {
            public uint Size;
            public int IsOffload;
            public AudioStreamCategory Category;
            public AudioClientStreamOptions Options;
        }

        private enum AudioStreamCategory { Other = 0 }
        [Flags] private enum AudioClientStreamOptions { Raw = 1 }
        private enum AudioClientShareMode { Shared = 0, Exclusive = 1 }
        [Flags] private enum AudioClientStreamFlags : uint { None = 0, NoPersist = 0x00080000 }
        [Flags] private enum AudioClientBufferFlags : uint { None = 0, DataDiscontinuity = 1, Silent = 2, TimestampError = 4 }
        private enum EDataFlow { Render = 0, Capture = 1, All = 2 }
        [Flags] private enum DeviceState : uint { Active = 1 }
        private enum StorageAccessMode { Read = 0 }
        [Flags] private enum ClsCtx : uint { InprocServer = 1, InprocHandler = 2, LocalServer = 4, RemoteServer = 16, All = 23 }

        [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
        private class MMDeviceEnumeratorComObject { }

        [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IMMDeviceEnumerator
        {
            [PreserveSig] int EnumAudioEndpoints(EDataFlow dataFlow, DeviceState stateMask, out IMMDeviceCollection devices);
            [PreserveSig] int GetDefaultAudioEndpoint(EDataFlow dataFlow, int role, out IMMDevice endpoint);
            [PreserveSig] int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string id, out IMMDevice device);
            [PreserveSig] int RegisterEndpointNotificationCallback(IntPtr client);
            [PreserveSig] int UnregisterEndpointNotificationCallback(IntPtr client);
        }

        [ComImport, Guid("0BD7A1BE-7A1A-44DB-8397-CC5392387B5E"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IMMDeviceCollection
        {
            [PreserveSig] int GetCount(out uint count);
            [PreserveSig] int Item(uint index, out IMMDevice device);
        }

        [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IMMDevice
        {
            [PreserveSig] int Activate(ref Guid iid, ClsCtx clsCtx, IntPtr activationParams, [MarshalAs(UnmanagedType.IUnknown)] out object interfacePointer);
            [PreserveSig] int OpenPropertyStore(StorageAccessMode accessMode, out IPropertyStore properties);
            [PreserveSig] int GetId([MarshalAs(UnmanagedType.LPWStr)] out string id);
            [PreserveSig] int GetState(out DeviceState state);
        }

        [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IPropertyStore
        {
            [PreserveSig] int GetCount(out uint count);
            [PreserveSig] int GetAt(uint index, out PropertyKey key);
            [PreserveSig] int GetValue(ref PropertyKey key, out PropVariant value);
            [PreserveSig] int SetValue(ref PropertyKey key, ref PropVariant value);
            [PreserveSig] int Commit();
        }

        [ComImport, Guid("726778CD-F60A-4EDA-82DE-E47610CD78AA"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IAudioClient2
        {
            [PreserveSig] int Initialize(AudioClientShareMode shareMode, AudioClientStreamFlags streamFlags, long bufferDuration, long periodicity, IntPtr format, ref Guid sessionGuid);
            [PreserveSig] int GetBufferSize(out uint bufferFrames);
            [PreserveSig] int GetStreamLatency(out long latency);
            [PreserveSig] int GetCurrentPadding(out uint paddingFrames);
            [PreserveSig] int IsFormatSupported(AudioClientShareMode shareMode, IntPtr format, out IntPtr closestMatch);
            [PreserveSig] int GetMixFormat(out IntPtr format);
            [PreserveSig] int GetDevicePeriod(out long defaultPeriod, out long minimumPeriod);
            [PreserveSig] int Start();
            [PreserveSig] int Stop();
            [PreserveSig] int Reset();
            [PreserveSig] int SetEventHandle(IntPtr eventHandle);
            [PreserveSig] int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object service);
            [PreserveSig] int IsOffloadCapable(AudioStreamCategory category, out int offloadCapable);
            [PreserveSig] int SetClientProperties(ref AudioClientProperties properties);
            [PreserveSig] int GetBufferSizeLimits(IntPtr format, int eventDriven, out long minimumBufferDuration, out long maximumBufferDuration);
        }

        [ComImport, Guid("C8ADBD64-E71E-48A0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IAudioCaptureClient
        {
            [PreserveSig] int GetBuffer(out IntPtr data, out uint frames, out AudioClientBufferFlags flags, out ulong devicePosition, out ulong qpcPosition);
            [PreserveSig] int ReleaseBuffer(uint frames);
            [PreserveSig] int GetNextPacketSize(out uint frames);
        }
    }
}
