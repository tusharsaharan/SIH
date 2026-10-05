Add-Type -AssemblyName System.Speech
$vos = @(
'Cyberattacks detonate in seconds. Defenses react after the damage is done. What if you could forecast an attack twenty minutes before it happens? Meet AegisForecast.',
'Today''s security centers are reactive. They store gigabytes of packet captures, drown in false positives, and detect intrusions only after data is stolen. We needed a system that predicts, not just detects.',
'AegisForecast folds live traffic into in-memory five second flow statistics. No pcap is ever written. A per-host Bi-LSTM with attention, challenged by a Transformer, watches forty eight windows and predicts attack probability, MITRE stage, and minutes to detonation.',
'On the live dashboard you see lateral movement across five hosts. WEB spikes to point nine nine eight risk while benign hosts stay at point zero one three. Every alert is explained with SHAP in six milliseconds, correlated into campaigns, and auto-contained by SOAR.',
'And it is proven, not claimed. Transformer A U C zero point nine eight five. One hundred percent coverage with twenty minute median lead time. Validated zero shot on real C I C I D S 2017 captures. Even stealth slow scans are caught.',
'AegisForecast. Forecast. Explain. Contain. Thank you.'
)
for ($i=0; $i -lt $vos.Length; $i++) {
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SelectVoice('Microsoft Zira Desktop')
  $s.Rate = -1
  $out = "C:\Users\tusha\AppData\Local\Temp\opencode\aegis_video\vo_offline_$i.wav"
  $s.SetOutputToWaveFile($out)
  $s.Speak($vos[$i])
  $s.Dispose()
  Write-Output "wrote $out"
}
