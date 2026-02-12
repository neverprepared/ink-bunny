class ShellProfiler < Formula
  desc "Workspace profile manager using direnv for environment-specific configurations"
  homepage "https://github.com/neverprepared/reflex"
  version "0.2.1"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/reflex/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-arm64.tar.gz"
      sha256 "6f14e8447ba7d4232c6877ead9417ea4f58efbd096fb7db598b6b8d215a995cf" # darwin-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/reflex/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-darwin-amd64.tar.gz"
      sha256 "4a9377d9c83ae1a9dd8c3e0745f7cf37cc5286fca8849101b3a2fcca71ef5f79" # darwin-amd64
    end
  end

  on_linux do
    if Hardware::CPU.arm?
      url "https://github.com/neverprepared/reflex/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-arm64.tar.gz"
      sha256 "336c51f52390acfe7eaaba194483679fc7828539014b7dc6e06cdcbabbee7af8" # linux-arm64
    end
    if Hardware::CPU.intel?
      url "https://github.com/neverprepared/reflex/releases/download/shell-profiler/v#{version}/shell-profiler-v#{version}-linux-amd64.tar.gz"
      sha256 "126ecc2e56404fe5d34914bd6cc9cc380ec73e3457f8eb06347077e3a8674e6a" # linux-amd64
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
