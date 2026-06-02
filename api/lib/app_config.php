<?php
/**
 * Load secrets from outside the public webroot.
 */
function appConfigPath(): string {
    $path = getenv('SPLITHUB_CONFIG_PATH') ?: dirname(__DIR__, 3) . '/config.php';
    if (!is_file($path)) {
        throw new RuntimeException('SPLITHUB_CONFIG_REQUIRED');
    }
    return $path;
}

require_once appConfigPath();
