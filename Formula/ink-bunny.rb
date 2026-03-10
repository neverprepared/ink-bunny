class InkBunny < Formula
  desc "Agentic development platform (brainbox + reflex + shell-profiler)"
  homepage "https://github.com/neverprepared/ink-bunny"
  # Points to an existing monorepo tag; nothing is installed from this archive.
  # Update url/sha256 when cutting a dedicated ink-bunny release.
  url "https://github.com/neverprepared/ink-bunny/archive/refs/tags/brainbox/v0.12.9.tar.gz"
  version "1.0.0"
  sha256 "5888a8c7450acd40ccec92cc7974ceae86412a4e1f999d094add60e33372b43a"
  license "MIT"

  depends_on "neverprepared/ink-bunny/brainbox"
  depends_on "neverprepared/ink-bunny/reflex"
  depends_on "neverprepared/ink-bunny/shell-profiler"

  def install
    # Meta-formula — all work done by dependencies
  end

  test do
    assert_path_exists HOMEBREW_PREFIX/"share/reflex/.claude-plugin/plugin.json"
  end
end
