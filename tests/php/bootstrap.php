<?php
function projectPath(string $path): string {
    return dirname(__DIR__, 2) . '/' . $path;
}

function assertTrue(bool $value, string $message): void {
    if (!$value) {
        throw new RuntimeException('FAIL: ' . $message);
    }
    echo "PASS: $message\n";
}

function assertSame(mixed $expected, mixed $actual, string $message): void {
    assertTrue($expected === $actual, $message);
}
