class Reflex < Formula
  desc "Claude Code plugin for development workflows, skills, and MCP management"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/reflex-v1.19.0/reflex-1.19.0.tar.gz"
  sha256 "b38ea77b61b26213b931b127bdd7cadf7dd1a05e1ac91ab8841261a49d2ef01c"
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
    assert_path_exists share/"reflex/.claude-plugin/plugin.json"
  end
end
