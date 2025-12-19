1. Nginx 容器：对外开放 80 端口。
2. PHP-FPM 容器：不对外，只通过共享卷中的 /run/php-fpm.sock 提供服务。

nginx-> php RCE
