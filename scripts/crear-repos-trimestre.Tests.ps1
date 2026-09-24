<#
    Guards the wrong-account footgun: crear-repos-trimestre.ps1 must refuse to run when the
    resolved owner isn't the expected personal account (e.g. gh authenticated into a company
    account instead of the personal one this course's repos live under).

    No gh calls are mocked here: -Owner is passed explicitly and -DryRun is used, so the
    script never reaches a real `gh repo view`/`gh repo create` call. The guard fires right
    after owner resolution, before anything else runs.
#>

$scriptPath = Join-Path $PSScriptRoot "crear-repos-trimestre.ps1"

Describe "crear-repos-trimestre: expected-owner guard" {

    BeforeEach {
        $inputsPath = Join-Path $TestDrive "trimestre-actual"
        New-Item -ItemType Directory -Path $inputsPath -Force | Out-Null
        Set-Content -Path (Join-Path $inputsPath "equipos.json") -Value '[{"team":"grupo-control","delegates":["some-delegate"]}]'
        $localDestination = Join-Path $TestDrive "local-repos"
    }

    It "throws when the resolved owner does not match -ExpectedOwner" {
        {
            & $scriptPath -Term "test" -Owner "IsaacNextep" -ExpectedOwner "IsaacBakugan" `
                -InputsPath $inputsPath -LocalDestination $localDestination -DryRun
        } | Should Throw "not the expected"
    }

    It "does not throw when the resolved owner matches -ExpectedOwner" {
        {
            & $scriptPath -Term "test" -Owner "IsaacBakugan" -ExpectedOwner "IsaacBakugan" `
                -InputsPath $inputsPath -LocalDestination $localDestination -DryRun
        } | Should Not Throw
    }

    It "does not throw when -ExpectedOwner is bypassed with an empty string" {
        {
            & $scriptPath -Term "test" -Owner "IsaacNextep" -ExpectedOwner "" `
                -InputsPath $inputsPath -LocalDestination $localDestination -DryRun
        } | Should Not Throw
    }
}
