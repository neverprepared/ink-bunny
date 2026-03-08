class ShellProfiler < Formula
  desc "Workspace profile manager using direnv for environment-specific configurations"
  homepage "https://github.com/neverprepared/ink-bunny"
  version "0.5.2"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-arm64.tar.gz"
      sha256 "75951896f7e87c3ed2ebbb42e8a3c76bce1dda90f07bc0c16bf5af2661104ce5" # darwin-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-amd64.tar.gz"
      sha256 "d26b9d3a68161c770e871cad8bee6b1288d626cc17532b9abc62ef12929eebfb" # darwin-amd64
    end
  end

  on_linux do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-arm64.tar.gz"
      sha256 "b3418d40dbb0d670940e843a45a056f1cf14ec924f80103f15ceb28408fe6cce" # linux-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/ink-bunny/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-amd64.tar.gz"
      sha256 "8d0550d069902e18ba39e677d85d6f01533d2b544bf8c98cada7c603fb15f13a" # linux-amd64
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
