$pem = [IO.File]::ReadAllText('D:\Services\dump-ledger-runtime\proxy-cert.pem')
$b64 = $pem -replace '-----BEGIN CERTIFICATE-----','' -replace '-----END CERTIFICATE-----','' -replace '\s',''
$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 -ArgumentList (,[Convert]::FromBase64String($b64))
$sha = [System.Security.Cryptography.SHA256]::Create()
$record = [ordered]@{account=[Environment]::UserName; subject=$cert.Subject; thumbprint_sha1=$cert.Thumbprint; fingerprint_sha256=([BitConverter]::ToString($sha.ComputeHash($cert.RawData))).Replace('-','').ToLower(); current_user_root=(Test-Path ('Cert:\CurrentUser\Root\'+$cert.Thumbprint)); local_machine_root=(Test-Path ('Cert:\LocalMachine\Root\'+$cert.Thumbprint)); not_after=$cert.NotAfter.ToUniversalTime().ToString('o'); endpoint='https://192.168.150.219:4080/symbols'}
$record | ConvertTo-Json | Set-Content -Encoding UTF8 'D:\Desktop\Workspaces\dump_03958DA4FCA844A786262A1053\frame-paths-20261013\certificate-trust.json'
$record | ConvertTo-Json
