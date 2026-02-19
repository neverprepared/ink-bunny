class Brainbox < Formula
  include Language::Python::Virtualenv

  desc "Sandboxed Docker container orchestration for Claude Code"
  homepage "https://github.com/neverprepared/ink-bunny"
  url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
  sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  license "MIT"

  depends_on "python@3.12"
  depends_on "docker" => :optional

  resource "fastapi" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "uvicorn" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "docker" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "pydantic" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "pydantic-settings" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "structlog" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "sse-starlette" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "questionary" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "rich" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "boto3" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "slowapi" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  resource "httpx" do
    url "https://github.com/neverprepared/ink-bunny/releases/download/brainbox/v0.6.0/brainbox-0.6.0.tar.gz"
    sha256 "ba8c56458dc27ade6bc4c47d60315821f15ec14174adbf1c8b0cbf131d0ba2c6"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "brainbox", shell_output("#{bin}/brainbox --help")
  end
end
