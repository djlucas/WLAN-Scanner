# Check if location services are enabled - Required
$locKey = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\location"
try {
    $locStatus = Get-ItemPropertyValue -Path $locKey -Name "Value" -ErrorAction Stop
    if ($locStatus -ne "Allow") {
        Write-Host "Location services are disabled. Wi-Fi scanning APIs require location access to function."
        Write-Host "Please enable location in Settings > Privacy & Security > Location before running this script."
        return
    }
} catch {
    Write-Host "Unable to verify location services status. This system may restrict access."
    Write-Host "Try enabling location manually if scanning fails."
    return
}


if ($debug -eq $NULL) {
    $debug = 0
}

if (-not ("WifiNative" -as [type])) {
    Add-Type -TypeDefinition @"
    using System;
    using System.Runtime.InteropServices;
    using System.Text;

    public class WifiNative {
        [StructLayout(LayoutKind.Sequential)]
        public struct DOT11_SSID {
            public uint uSSIDLength;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 32)]
            public byte[] ucSSID;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 4)]  // ← test pad
            public byte[] alignmentPad;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct WLAN_BSS_ENTRY {
            public DOT11_SSID dot11Ssid;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)]
            public byte[] dot11Bssid;
            public uint dot11BssType;
            public uint dot11BssPhyType;
            public int lRssi;
            public byte uLinkQuality;
            [MarshalAs(UnmanagedType.Bool)] public bool bInRegDomain;
            public ushort usBeaconPeriod;
            public ulong ullTimestamp;
            public ulong ullHostTimestamp;
            public ushort usCapabilityInformation;
            public uint ulChCenterFrequency;
            public uint ulPhyRate;
            [MarshalAs(UnmanagedType.ByValArray, SizeConst = 256)]
            public byte[] reserved;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct WLAN_INTERFACE_INFO_LIST {
            public int dwNumberOfItems;
            public int dwIndex;
            public IntPtr InterfaceInfo;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        public struct WLAN_INTERFACE_INFO {
            public Guid InterfaceGuid;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)]
            public string strInterfaceDescription;
            public uint isState;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct WLAN_BSS_LIST {
            public uint dwTotalSize;
            public uint dwNumberOfItems;
            public IntPtr wlanBssEntries;
        }

        public enum WLAN_INTF_OPCODE {
            wlan_intf_opcode_current_connection = 0x0000000E
        }

        public enum WLAN_OPCODE_VALUE_TYPE {
            QueryOnly = 0,
            SetByGroupPolicy,
            SetByUser,
            Invalid
        }

        [DllImport("wlanapi.dll")]
        public static extern int WlanOpenHandle(uint dwClientVersion, IntPtr pReserved, out uint pdwNegotiatedVersion, out IntPtr phClientHandle);

        [DllImport("wlanapi.dll")]
        public static extern int WlanEnumInterfaces(IntPtr hClientHandle, IntPtr pReserved, out IntPtr ppInterfaceList);

        [DllImport("wlanapi.dll")]
        public static extern int WlanScan(IntPtr hClientHandle, ref Guid pInterfaceGuid, IntPtr pDot11Ssid, IntPtr pIeData, IntPtr pReserved);

        [DllImport("wlanapi.dll")]
        public static extern int WlanGetNetworkBssList(IntPtr hClientHandle, ref Guid pInterfaceGuid, IntPtr pDot11Ssid, uint dot11BssType, bool bSecurityEnabled, IntPtr pReserved, out IntPtr ppWlanBssList);

        [DllImport("wlanapi.dll")]
        public static extern void WlanFreeMemory(IntPtr pMemory);

        public static Guid[] GetWirelessGuids(IntPtr hClient) {
            IntPtr pList;
            WlanEnumInterfaces(hClient, IntPtr.Zero, out pList);
            WLAN_INTERFACE_INFO_LIST list = Marshal.PtrToStructure<WLAN_INTERFACE_INFO_LIST>(pList);
            Guid[] guids = new Guid[list.dwNumberOfItems];
            long basePtr = pList.ToInt64() + Marshal.SizeOf(typeof(WLAN_INTERFACE_INFO_LIST)) - IntPtr.Size;
            for (int i = 0; i < list.dwNumberOfItems; i++) {
                WLAN_INTERFACE_INFO info = Marshal.PtrToStructure<WLAN_INTERFACE_INFO>(
                    new IntPtr(basePtr + i * Marshal.SizeOf(typeof(WLAN_INTERFACE_INFO))));
                guids[i] = info.InterfaceGuid;
            }
            WlanFreeMemory(pList);
            return guids;
        }

        public static WLAN_BSS_ENTRY[] GetBssList(IntPtr hClient, Guid interfaceGuid) {
            IntPtr pList;
            int result = WlanGetNetworkBssList(hClient, ref interfaceGuid, IntPtr.Zero, 0, false, IntPtr.Zero, out pList);
            if (result != 0 || pList == IntPtr.Zero) return new WLAN_BSS_ENTRY[0];

            WLAN_BSS_LIST list = Marshal.PtrToStructure<WLAN_BSS_LIST>(pList);
            int entrySize = Marshal.SizeOf(typeof(WLAN_BSS_ENTRY));
            long basePtr = pList.ToInt64() + Marshal.OffsetOf(typeof(WLAN_BSS_LIST), "wlanBssEntries").ToInt64();

            WLAN_BSS_ENTRY[] entries = new WLAN_BSS_ENTRY[list.dwNumberOfItems];
            for (int i = 0; i < list.dwNumberOfItems; i++) {
                IntPtr entryPtr = new IntPtr(basePtr + i * entrySize);
                entries[i] = Marshal.PtrToStructure<WLAN_BSS_ENTRY>(entryPtr);
            }

            WlanFreeMemory(pList);
            return entries;
        }

        public static string FormatMac(byte[] mac) {
            return (mac != null && mac.Length == 6) ? BitConverter.ToString(mac) : "??";
        }

        public static string FormatSsid(DOT11_SSID ssid) {
            int len = (int)ssid.uSSIDLength;
            if (len == 0) return "{Hidden}";
            if (ssid.ucSSID == null || len < 0 || len > ssid.ucSSID.Length) return "";
            return Encoding.ASCII.GetString(ssid.ucSSID, 0, len);
        }

        public static string FormatQuality(byte quality) {
            return (quality > 100) ? "??" : quality.ToString();
        }
    }
"@ -Language CSharp
}

# Open WLAN client
$clientHandle = [IntPtr]::Zero
$negotiatedVersion = 0
[WifiNative]::WlanOpenHandle(2, [IntPtr]::Zero, [ref]$negotiatedVersion, [ref]$clientHandle) | Out-Null

# Scan interfaces
$guids = [WifiNative]::GetWirelessGuids($clientHandle)

if ($debug -eq 1) {
    $guids | ForEach-Object { Write-Host "Interface GUID: $_" }
}

foreach ($guid in $guids) {
    [WifiNative]::WlanScan($clientHandle, [ref]$guid, [IntPtr]::Zero, [IntPtr]::Zero, [IntPtr]::Zero) | Out-Null
}

# Wait 5 seconds for scan to complete
Start-Sleep -Seconds 5

# Parse and display results
$results = @()
foreach ($guid in $guids) {
    $entries = [WifiNative]::GetBssList($clientHandle, $guid)

    if ($debug -eq 1) {
        Write-Host "DEBUG: Found $($entries.Length) BSS entries for $guid"
    }

    foreach ($entry in $entries) {
        $ssid    = [WifiNative]::FormatSsid($entry.dot11Ssid)
        $mac     = [WifiNative]::FormatMac($entry.dot11Bssid)
        $quality = [WifiNative]::FormatQuality($entry.uLinkQuality)
        $freqMHz = [math]::Round($entry.ulChCenterFrequency / 1000)

        # Convert frequency to channel
        if ($freqMHz -ge 2400 -and $freqMHz -lt 2500) {
            $channel = [math]::Round(($freqMHz - 2407) / 5)
            $band = "2.4 GHz"
        }
        elseif ($freqMHz -ge 5000 -and $freqMHz -lt 5900) {
            $channel = [math]::Round(($freqMHz - 5000) / 5)
            $band = "5 GHz"
        }
        elseif ($freqMHz -ge 5955 -and $freqMHz -lt 7125) {
            $channel = [math]::Round(($freqMHz - 5955) / 5)
            $band = "6 GHz"
        }
        else {
            $channel = "?"
            $band = "?"
        }

    if ($debug -eq 1) {
        $ssidHex   = [BitConverter]::ToString($entry.dot11Ssid.ucSSID)
        $bssidHex  = [BitConverter]::ToString($entry.dot11Bssid)
        $reservedHead = [BitConverter]::ToString($entry.reserved[0..31])

        Write-Host "SSID Bytes → $ssidHex"
        Write-Host "BSSID → $bssidHex"
        Write-Host "Reserved (first 32 bytes) → $reservedHead"
        Write-Host ("Raw Entry >> SSID: {0}, BSSID: {1}, RSSI: {2}, Quality: {3}, Freq: {4}" -f $ssid, $mac, $entry.lRssi, $quality, $entry.ulChCenterFrequency)
    }

        $results += [PSCustomObject]@{
            SSID    = $ssid
            BSSID   = $mac
            RSSI    = $entry.lRssi
            Quality = $quality
            Frequency = [int]$freqMHz
            Channel = [int]$channel
            Band      = $band
        }
    }
}

$results | Sort -Descending -Property RSSI | ConvertTo-Json -Depth 3
