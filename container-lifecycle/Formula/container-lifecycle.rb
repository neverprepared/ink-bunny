class ContainerLifecycle < Formula
  include Language::Python::Virtualenv

  desc "Sandboxed Docker container orchestration for Claude Code"
  homepage "https://github.com/neverprepared/reflex"
  url "https://github.com/neverprepared/reflex/releases/download/container-lifecycle/v0.2.0/container-lifecycle-0.2.0.tar.gz"
  sha256 "c052e43678e0c7cb81b692909018bf654ab186ef7f374a80e73ebf49fa560101"
  license "MIT"

  depends_on "python@3.12"
  depends_on "docker" => :optional

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "container-lifecycle", shell_output("#{bin}/container-lifecycle --help")
  end
end
