#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# WLAN Scanner
#
# app/interference_analyzer.py
#
# Description:
# Interference analysis engine for detecting and analyzing WiFi interference
# patterns, channel conflicts, and signal overlap issues.
# -----------------------------------------------------------------------------

from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional
from .data_models import Floor, ScanPoint, APData, PlacedAP


class InterferenceReport:
    """Container for interference analysis results"""

    def __init__(self):
        self.channel_usage: Dict[int, int] = {}
        self.strong_interferers: Dict[int, List[Tuple[str, int]]] = defaultdict(list)  # channel -> [(ssid, max_rssi)]
        self.overlap_interference: Dict[int, List[Tuple[int, str, int]]] = defaultdict(list)  # channel -> [(interfering_ch, ssid, rssi)]
        self.problem_areas: List[Tuple[int, int, int, int, List[Tuple[str, int, int]]]] = []  # (x, y, target_rssi, interferer_count, interferers)
        self.target_network_channels: List[int] = []
        self.total_detections: int = 0


class InterferenceAnalyzer:
    """
    Analyzes WiFi interference patterns from scan data
    """

    def __init__(self, target_network_prefixes: List[str] = None):
        """
        Initialize the interference analyzer

        Args:
            target_network_prefixes: List of SSID prefixes to consider as target network
                                   (e.g., ['LITS', 'Corporate']) - defaults to auto-detect
        """
        self.target_network_prefixes = target_network_prefixes or []
        self.interference_threshold = -70  # dBm - signals stronger than this can cause interference
        self.overlap_threshold = -70  # dBm - signals stronger than this in overlapping channels

    def analyze_floor(self, floor: Floor, target_network_name: str = None) -> InterferenceReport:
        """
        Analyze interference patterns for a floor

        Args:
            floor: Floor object containing scan data
            target_network_name: Specific network to analyze (auto-detects if None)

        Returns:
            InterferenceReport with analysis results
        """
        report = InterferenceReport()

        # Collect all network detections
        all_networks = []
        for scan_point in floor.scan_points:
            all_networks.extend(scan_point.ap_list)

        report.total_detections = len(all_networks)

        # Determine target network
        if target_network_name:
            target_prefixes = [target_network_name]
        else:
            target_prefixes = self._auto_detect_target_network(all_networks)

        # Identify target network channels
        target_channels = set()
        for network in all_networks:
            if any(network.ssid.startswith(prefix) for prefix in target_prefixes):
                target_channels.add(network.channel)

        report.target_network_channels = sorted(target_channels)

        # Analyze channel usage
        report.channel_usage = self._analyze_channel_usage(all_networks)

        # Find strong interferers
        report.strong_interferers = self._find_strong_interferers(
            all_networks, target_prefixes
        )

        # Analyze channel overlap interference (primarily 2.4GHz)
        report.overlap_interference = self._analyze_overlap_interference(all_networks)

        # Find problem areas with good target signal but high interference
        report.problem_areas = self._find_problem_areas(
            floor.scan_points, target_prefixes
        )

        return report

    def _auto_detect_target_network(self, networks: List[APData]) -> List[str]:
        """
        Auto-detect the target network by finding networks with strongest signals
        and consistent presence across scan points
        """
        if self.target_network_prefixes:
            return self.target_network_prefixes

        # Count SSID occurrences and track strongest signals
        ssid_stats = defaultdict(lambda: {'count': 0, 'max_signal': -100, 'min_signal': 0})

        for network in networks:
            if network.ssid and network.ssid != "{Hidden}":
                ssid = network.ssid
                ssid_stats[ssid]['count'] += 1
                ssid_stats[ssid]['max_signal'] = max(ssid_stats[ssid]['max_signal'], network.signal_strength)
                ssid_stats[ssid]['min_signal'] = min(ssid_stats[ssid]['min_signal'], network.signal_strength)

        # Score networks by presence and signal strength
        candidates = []
        for ssid, stats in ssid_stats.items():
            if stats['count'] >= 10 and stats['max_signal'] > -30:  # Frequent and strong
                # Higher score for more detections and stronger signals
                score = stats['count'] * (100 + stats['max_signal'])  # Signal strength is negative
                candidates.append((ssid, score, stats))

        if candidates:
            # Sort by score and return the best candidate's prefix
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_ssid = candidates[0][0]

            # Extract prefix for related networks (e.g., LITS, LITS-Guest, LITS-IOT)
            parts = best_ssid.replace('-', ' ').replace('_', ' ').split()
            if parts:
                return [parts[0]]

        return []

    def _analyze_channel_usage(self, networks: List[APData]) -> Dict[int, int]:
        """
        Count network detections per channel
        """
        channel_usage = Counter()
        for network in networks:
            channel_usage[network.channel] += 1

        return dict(channel_usage)

    def _find_strong_interferers(self, networks: List[APData],
                               target_prefixes: List[str]) -> Dict[int, List[Tuple[str, int]]]:
        """
        Find non-target networks with strong signals that could cause interference
        Excludes same physical device (grouped by BSSID bytes 1-4)
        """
        strong_interferers = defaultdict(list)

        # Group all networks by device
        device_groups = self._group_networks_by_device(networks)

        # Identify target device IDs
        target_device_ids = set()
        for device_id, device_networks in device_groups.items():
            for network in device_networks:
                if any(network.ssid.startswith(prefix) for prefix in target_prefixes):
                    target_device_ids.add(device_id)
                    break

        # Find strong interferers from non-target devices
        for device_id, device_networks in device_groups.items():
            # Skip if this is a target device
            if device_id in target_device_ids:
                continue

            # Process each network in this device
            for network in device_networks:
                # Skip hidden networks
                if network.ssid == "{Hidden}":
                    continue

                if network.signal_strength > self.interference_threshold:
                    # Use SSID and signal strength for this device/network
                    strong_interferers[network.channel].append((network.ssid, network.signal_strength))

        # Sort by signal strength and remove duplicates per channel
        for channel in strong_interferers:
            # Group by SSID to keep strongest signal per SSID
            by_ssid = defaultdict(list)
            for ssid, signal in strong_interferers[channel]:
                by_ssid[ssid].append(signal)

            # Keep strongest signal per SSID
            channel_interferers = [(ssid, max(signals)) for ssid, signals in by_ssid.items()]
            channel_interferers.sort(key=lambda x: x[1], reverse=True)
            strong_interferers[channel] = channel_interferers

        return dict(strong_interferers)

    def _analyze_overlap_interference(self, networks: List[APData]) -> Dict[int, List[Tuple[int, str, int]]]:
        """
        Find interference from overlapping channels (primarily 2.4GHz)
        Excludes same physical device (grouped by BSSID bytes 1-4)
        """
        overlap_interference = defaultdict(list)

        # Group all networks by device
        device_groups = self._group_networks_by_device(networks)

        # Find strong signals per channel in 2.4GHz band, grouped by device
        strong_24ghz_by_device = defaultdict(lambda: defaultdict(list))  # device_id -> channel -> [(ssid, rssi)]

        for device_id, device_networks in device_groups.items():
            for network in device_networks:
                if (network.channel <= 14 and
                    network.signal_strength > self.overlap_threshold and
                    network.ssid != "{Hidden}"):
                    strong_24ghz_by_device[device_id][network.channel].append((network.ssid, network.signal_strength))

        # Check for overlapping interference between different devices
        device_ids = list(strong_24ghz_by_device.keys())
        for i, device_id1 in enumerate(device_ids):
            for device_id2 in device_ids[i+1:]:  # Only check each pair once
                # Check all channel combinations between these two devices
                for channel1, networks1 in strong_24ghz_by_device[device_id1].items():
                    for channel2, networks2 in strong_24ghz_by_device[device_id2].items():
                        if channel1 != channel2 and self._channels_overlap(channel1, channel2):
                            # Add interference from device2 affecting device1's channel
                            for ssid2, rssi2 in networks2:
                                if rssi2 > self.overlap_threshold:
                                    overlap_interference[channel1].append((channel2, ssid2, rssi2))

                            # Add interference from device1 affecting device2's channel
                            for ssid1, rssi1 in networks1:
                                if rssi1 > self.overlap_threshold:
                                    overlap_interference[channel2].append((channel1, ssid1, rssi1))

        # Sort by signal strength and remove duplicates
        for channel in overlap_interference:
            # Remove duplicates and sort
            unique_interference = list(set(overlap_interference[channel]))
            unique_interference.sort(key=lambda x: x[2], reverse=True)
            overlap_interference[channel] = unique_interference

        return dict(overlap_interference)

    def _channels_overlap(self, ch1: int, ch2: int) -> bool:
        """
        Check if two 2.4GHz channels overlap significantly

        2.4GHz channels are spaced 5MHz apart but use 20MHz bandwidth,
        so channels overlap unless they're at least 5 channels apart.
        Standard non-overlapping channels are 1, 6, 11.
        """
        if ch1 > 14 or ch2 > 14:  # 5GHz channels have different overlap rules
            return False

        return abs(ch1 - ch2) < 5

    def _get_device_id(self, bssid: str) -> str:
        """
        Extract device identifier from BSSID (bytes 1-4)

        Assumes same physical device if bytes 1-4 are identical.
        Returns the middle 4 bytes as device identifier.
        """
        if not bssid:
            return ""

        try:
            octets = bssid.replace('-', ':').split(':')
            if len(octets) != 6:
                return ""

            # Return bytes 1-4 (indices 1-4) as device identifier
            return ':'.join(octets[1:5]).upper()
        except (ValueError, IndexError):
            return ""

    def _group_networks_by_device(self, networks: List[APData]) -> Dict[str, List[APData]]:
        """
        Group networks by physical device based on BSSID bytes 1-4

        Returns:
            Dict mapping device_id to list of APData for that device
        """
        device_groups = defaultdict(list)

        for network in networks:
            device_id = self._get_device_id(network.bssid)
            if device_id:
                device_groups[device_id].append(network)

        return dict(device_groups)

    def _find_problem_areas(self, scan_points: List[ScanPoint],
                          target_prefixes: List[str]) -> List[Tuple[int, int, int, int, List[Tuple[str, int, int]]]]:
        """
        Find areas with good target network coverage but significant interference
        """
        problem_areas = []

        for scan_point in scan_points:
            # Find strongest target network signal at this location
            target_signal = None
            for network in scan_point.ap_list:
                if any(network.ssid.startswith(prefix) for prefix in target_prefixes):
                    if target_signal is None or network.signal_strength > target_signal:
                        target_signal = network.signal_strength

            # Count strong interfering signals (non-target, non-hidden, different device)
            strong_interferers = []

            # Group networks at this scan point by device
            device_groups = self._group_networks_by_device(scan_point.ap_list)

            # Identify target device IDs at this location
            target_device_ids = set()
            for device_id, device_networks in device_groups.items():
                for network in device_networks:
                    if any(network.ssid.startswith(prefix) for prefix in target_prefixes):
                        target_device_ids.add(device_id)
                        break

            # Find interferers from non-target devices
            for device_id, device_networks in device_groups.items():
                # Skip if this is a target device
                if device_id in target_device_ids:
                    continue

                # Find strongest interfering signal from this device
                device_interferers = []
                for network in device_networks:
                    if (network.signal_strength > self.interference_threshold and
                        network.ssid != "{Hidden}"):
                        device_interferers.append((network.ssid, network.channel, network.signal_strength))

                # Add strongest signal from this device
                if device_interferers:
                    strongest = max(device_interferers, key=lambda x: x[2])
                    strong_interferers.append(strongest)

            # Mark as problem area if good target signal but multiple interferers
            if (target_signal and target_signal > -60 and len(strong_interferers) >= 2):
                # Sort interferers by signal strength
                strong_interferers.sort(key=lambda x: x[2], reverse=True)
                problem_areas.append((
                    int(scan_point.map_x),
                    int(scan_point.map_y),
                    target_signal,
                    len(strong_interferers),
                    strong_interferers[:5]  # Top 5 interferers
                ))

        return problem_areas

    def generate_summary(self, report: InterferenceReport, networks: List[APData] = None) -> str:
        """
        Generate a text summary of interference analysis
        """
        lines = []
        lines.append("=== INTERFERENCE ANALYSIS SUMMARY ===")
        lines.append(f"Total network detections: {report.total_detections}")
        lines.append(f"Target network channels: {report.target_network_channels}")

        # Add device grouping summary if networks provided
        if networks:
            device_groups = self._group_networks_by_device(networks)
            unique_devices = len(device_groups)
            lines.append(f"Unique physical devices detected: {unique_devices}")

            # Show device breakdown
            lines.append("")
            lines.append("Device Groups (by BSSID bytes 1-4):")
            for device_id, device_networks in sorted(device_groups.items()):
                ssids = set(net.ssid for net in device_networks if net.ssid != "{Hidden}")
                bssids = [net.bssid for net in device_networks]
                lines.append(f"  Device {device_id}:")
                lines.append(f"    SSIDs: {', '.join(sorted(ssids)) if ssids else 'Hidden only'}")
                lines.append(f"    BSSIDs: {', '.join(sorted(bssids))}")
                channels = sorted(set(net.channel for net in device_networks))
                lines.append(f"    Channels: {channels}")

        lines.append("")

        # Channel usage summary
        if report.channel_usage:
            lines.append("Channel Usage:")
            for ch in sorted(report.channel_usage.keys()):
                count = report.channel_usage[ch]
                band = "2.4GHz" if ch <= 14 else "5GHz"
                lines.append(f"  CH{ch} ({band}): {count} detections")

        lines.append("")

        # Strong interferers
        if report.strong_interferers:
            lines.append("Strong Interfering Networks:")
            for ch in sorted(report.strong_interferers.keys()):
                if ch in report.target_network_channels:
                    lines.append(f"  Channel {ch} (TARGET CHANNEL):")
                else:
                    lines.append(f"  Channel {ch}:")

                for ssid, rssi in report.strong_interferers[ch][:3]:
                    lines.append(f"    {ssid}: {rssi}dBm")

        lines.append("")

        # Overlap interference
        if report.overlap_interference:
            lines.append("Channel Overlap Interference (2.4GHz):")
            for ch in sorted(report.overlap_interference.keys()):
                lines.append(f"  Channel {ch}:")
                for other_ch, ssid, rssi in report.overlap_interference[ch][:3]:
                    lines.append(f"    CH{other_ch}: {ssid} ({rssi}dBm)")

        lines.append("")

        # Problem areas
        if report.problem_areas:
            lines.append("Problem Areas (Good signal + High interference):")
            for x, y, target_rssi, interferer_count, interferers in report.problem_areas:
                lines.append(f"  Location ({x}, {y}): Target {target_rssi}dBm, {interferer_count} interferers")
                for ssid, ch, rssi in interferers[:2]:
                    lines.append(f"    {ssid} (CH{ch}): {rssi}dBm")
        else:
            lines.append("No significant interference issues detected.")

        return "\n".join(lines)