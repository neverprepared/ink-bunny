class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/reflex/v1.8.0/reflex-1.8.0.tar.gz"
  sha256 "9538b1e0b613626135a798dd151c2100f03d41b1d794f93943682177b237cdbc"
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
