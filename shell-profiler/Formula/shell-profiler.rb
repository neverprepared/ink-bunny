class ShellProfiler < Formula
  desc "Workspace profile manager using direnv for environment-specific configurations"
  homepage "https://github.com/neverprepared/numa"
  version "0.2.1"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/numa/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-arm64.tar.gz"
      sha256 "a65e216ededcbaf79c730f30b754e4fc248d06cae0307ea3d7d1f1cf5e0e7730" # darwin-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/numa/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-amd64.tar.gz"
      sha256 "f33be32714bae6188def2dd81b0b7931e2e3c59987313f27962d6207e8a47052" # darwin-amd64
    end
  end

  on_linux do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/numa/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-arm64.tar.gz"
      sha256 "88488a5efb3963790bac9a69eeb1c831da7a26f3f2106cf5797046aa7f96d9c7" # linux-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/numa/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-amd64.tar.gz"
      sha256 "061be1a9a5aa8c25f54c4ab23a52dbd12bed5e7c4bb1bf2c109e85ba34f49e6a" # linux-amd64
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
