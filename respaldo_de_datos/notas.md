1. Comando para crear el respaldo (Exportar)
Bash
docker exec -i "NOMBRE_DE_TU_CONTENEDOR" mariadb-dump -u root -p"CONTRASEÑA_ROOT_BASE_DATOS" "NOMBRE_DE_LA_BASE_DATOS" > respaldo_kiosco_mariadb.sql

2. Comando para restaurar el respaldo (Importar)
Bash
docker exec -i "NOMBRE_DE_TU_CONTENEDOR" mariadb -u root -p"CONTRASEÑA_ROOT_BASE_DATOS" "NOMBRE_DE_LA_BASE_DATOS" < respaldo_kiosco_mariadb.sql