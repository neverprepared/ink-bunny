class Brainbox < Formula
  include Language::Python::Virtualenv

  desc "Sandboxed Docker container orchestration for Claude Code"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.3.0/brainbox-0.3.0.tar.gz"
  sha256 "2eb93f471bf5169052ca3cc2907065bb3e5df65ecc5fab65a664f49fd8eefc23"
  license "MIT"

  depends_on "python@3.12"
  depends_on "docker" => :optional

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "brainbox", shell_output("#{bin}/brainbox --help")
  end
end
