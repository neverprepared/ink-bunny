class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/reflex-v1.13.2/reflex-1.13.2.tar.gz"
  sha256 "152fff5a5d48fc727c8233d39538fa4243728b0548811333f11e43badc653a6c"
  license "MIT"

  def install
    (share/"reflex").install Dir["plugins/reflex/*"]
  end

  def caveats
    <<~EOS
      To use reflex with Claude Code:

        claude --plugin-dir #{share}/reflex

      Or install from the plugin marketplace:

        /plugin marketplace add mindmorass/reflex
    EOS
  end

  test do
    assert_predicate share/"reflex/.claude-plugin/plugin.json", :exist?
  end
end
