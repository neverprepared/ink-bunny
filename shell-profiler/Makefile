.PHONY: build install clean test

# Build the Go binary
build:
	go build -o shell-profiler ./cmd/shell-profiler

# Install the binary to the workspace root
install: build
	cp shell-profiler $(shell pwd)/shell-profiler

# Clean build artifacts
clean:
	rm -f shell-profiler
	go clean

# Run tests
test:
	go test ./...

# Run the binary directly
run:
	go run ./cmd/shell-profiler

