class BrainboxDocker < Formula
  desc "Docker wrapper for brainbox - sandboxed Claude Code session manager"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
  sha256 "ac05ee2b46b85cb8b58527d4e5e6e4d7926c0946976cea5cbff72646fa537e6f"
  license "MIT"

  depends_on "docker"

  def install
    # Install wrapper script
    bin.install "scripts/brainbox"
  end

  def caveats
    <<~EOS
      brainbox requires Docker to run. Please ensure Docker Desktop is running:
        open -a Docker

      The first time you run brainbox, it will download the Docker image.

      Usage:
        brainbox --help
        brainbox provision myproject
        brainbox api

      Configuration is stored in ~/.config/brainbox
    EOS
  end

  test do
    # Test that Docker requirement is enforced
    system "#{bin}/brainbox", "--help" if system "docker", "info"
  end
end
