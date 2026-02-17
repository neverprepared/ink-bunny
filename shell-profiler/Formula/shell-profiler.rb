class ShellProfiler < Formula
  desc "Workspace profile manager using direnv for environment-specific configurations"
  homepage "https://github.com/neverprepared/ink-bunny"
  version "0.4.0"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-arm64.tar.gz"
      sha256 "fb5cdec889ee6e734afc4127ba76017eacc4e67ad3456d1ae3249c7ac5c9495f" # darwin-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-amd64.tar.gz"
      sha256 "3c517a811d390481c5284e97edc90b8efc4331a344d1dae9f1719405792d4a60" # darwin-amd64
    end
  end

  on_linux do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-arm64.tar.gz"
      sha256 "b77bc06277a9b9a387f1b65a9a8fd33ffb553104120a3656db4029a4fa6ae5bd" # linux-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-amd64.tar.gz"
      sha256 "7ae90ad6eaaf70dac86db7c3f41ce57086668a49ccafce6070fc3f84df4c604b" # linux-amd64
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
