class Brainbox < Formula
  include Language::Python::Virtualenv

  desc "Sandboxed Docker container orchestration for Claude Code"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.5.0/brainbox-0.5.0.tar.gz"
  sha256 "2d4ccdca805065e32d3af1be27c5cbced85b499662a928a58ec1768d9f53488e"
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
