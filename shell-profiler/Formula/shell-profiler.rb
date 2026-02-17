class ShellProfiler < Formula
  desc "Workspace profile manager using direnv for environment-specific configurations"
  homepage "https://github.com/neverprepared/ink-bunny"
  version "0.5.0"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-arm64.tar.gz"
      sha256 "ea183dd95288adfbff6172f4ca5c2ecdab9fba8c8a64fa2066adb839070e2c8f" # darwin-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-amd64.tar.gz"
      sha256 "e2c47fd645488ea937182eb161e1fb5788f1529dec505dc40d164a65b57e70d3" # darwin-amd64
    end
  end

  on_linux do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-arm64.tar.gz"
      sha256 "b961ea82a5933af92d359da32f44dbd279e4a99fc485247bff10648cca49546d" # linux-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-amd64.tar.gz"
      sha256 "32b8035f66052a03661da69f2e09215a3ec85d439b622864314754aa70561007" # linux-amd64
    end
  end

  depends_on "direnv"

  def install
    bin.install "shell-profiler"
  end

  test do
    assert_match "Workspace Profile Manager", shell_output("#{bin}/shell-profiler help")
  end
end
