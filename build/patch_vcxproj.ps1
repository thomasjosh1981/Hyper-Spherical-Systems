$dict_line = '    <ClCompile Include="C:\Users\twist\workspace\hyper_spherical_systems\src\dictionary_store.cpp" />'
$old_line   = '    <ClCompile Include="C:\Users\twist\workspace\hyper_spherical_systems\src\static_dictionary.cpp" />'
$insert_after = $old_line

Get-ChildItem "C:\Users\twist\workspace\hyper_spherical_systems\build\*.vcxproj" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -notmatch [regex]::Escape($dict_line)) {
        $content = $content.Replace($insert_after, "$insert_after`r`n$dict_line")
        Set-Content -Path $_.FullName -Value $content -NoNewline
        Write-Host "Updated: $($_.Name)"
    } else {
        Write-Host "Already present: $($_.Name)"
    }
}
