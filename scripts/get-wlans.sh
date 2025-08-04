#!/bin/bash

scan_mac() {
  /System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport -s |
  awk 'NR>1 { print "{\"ssid\":\""$1"\",\"bssid\":\""$2"\",\"rssi\":"$3"}," }' |
  sed '$ s/,$//' | awk 'BEGIN{ print "[" } { print } END{ print "]" }'
}

scan_nmcli() {
  nmcli -t -f SSID,BSSID,SIGNAL dev wifi |
  awk -F: '{ print "{\"ssid\":\""$1"\",\"bssid\":\""$2"\",\"rssi\":"$3"}," }' |
  sed '$ s/,$//' | awk 'BEGIN{ print "[" } { print } END{ print "]" }'
}

scan_iwlist() {
  sudo iwlist scan 2>/dev/null |
  awk '/Cell|ESSID|Signal level/ { 
    if (/Cell/) bssid=$5; 
    if (/ESSID/) ssid=substr($0, index($0,$2)); 
    if (/Signal level/) rssi=$4; 
    if (bssid && ssid && rssi) {
      print "{\"ssid\":"ssid",\"bssid\":\""bssid"\",\"rssi\":"rssi"},";
      bssid=""; ssid=""; rssi=""
    }
  }' | sed '$ s/,$//' | awk 'BEGIN{ print "[" } { print } END{ print "]" }'
}

main() {
  unameOut="$(uname -s)"
  case "${unameOut}" in
    Darwin*) scan_mac ;;
    Linux*)
      if command -v nmcli > /dev/null; then
        scan_nmcli
      else
        scan_iwlist
      fi
      ;;
    *) echo "[]" ;;
  esac
}

main
