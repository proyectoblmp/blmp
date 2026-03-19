# Guía de deploy y migraciones — BLMP
**Servidor:** `dti@blmp` — https://blmp.unl.edu.ec/
**Proyecto:** `~/proyectos/catalogacion-musical/`
**Virtualenv:** `~/.virtualenvs/blmp_env/`
**Logs:** `/var/log/blmp/gunicorn_web_error.log`

---

## Deploy normal (después de un fix en local)

### 1. Subir el código al repo desde local
```bash
git add <archivos>
git commit -m "fix: descripción del cambio"
git push origin main
```

### 2. Ejecutar el deploy en el servidor
```bash
$ ssh -p 4287 dti@blmp.unl.edu.ec
bash ~/proyectos/catalogacion-musical/deploy.sh
```

El script hace automáticamente:
- `git pull origin main`
- `pip install -r requirements.txt`
- `python manage.py migrate`
- `python manage.py collectstatic`
- Reinicio de Gunicorn

**Opciones:**
```bash
bash deploy.sh --skip-pip       # Salta pip (más rápido si no cambiaron dependencias)
bash deploy.sh --restart-nginx  # También reinicia Nginx
```

---

## Diagnóstico de errores comunes

### Ver errores en tiempo real
```bash
tail -f /var/log/blmp/gunicorn_web_error.log
```

### Verificar estado de Gunicorn
```bash
pgrep -a -f blmp_web_gunicorn
```

### Verificar estado de migraciones
```bash
cd ~/proyectos/catalogacion-musical
source ~/.virtualenvs/blmp_env/bin/activate
python manage.py showmigrations
```

---

## Problemas de migraciones — guía de decisión

### Error: "no existe la columna X"
La columna está en el modelo pero no en la BD. La migración que la crea fue marcada como fake o nunca se aplicó.

```bash
# Ver qué migraciones tiene registradas la BD para esa app
python manage.py showmigrations <app>

# Desmarcar la migración problemática y reaplicar de verdad
python manage.py dbshell
```
```sql
DELETE FROM django_migrations WHERE app='<app>' AND name='<migracion>';
\q
```
```bash
python manage.py migrate <app>
```

---

### Error: "ya existe la columna X" (DuplicateColumn)
La columna ya está en la BD pero Django intenta crearla de nuevo porque no está registrada en `django_migrations`.

```bash
# Fakear hasta la migración que ya está aplicada en BD
python manage.py migrate --fake <app> <numero_migracion>
# Ejemplo: hasta 0003 inclusive
python manage.py migrate --fake usuarios 0003

# Luego aplicar las siguientes de verdad
python manage.py migrate <app>
```

---

### Error: "Conflicting migrations / multiple leaf nodes"
Hay dos ramas de migraciones que parten del mismo punto. Ocurre cuando se generan migraciones directamente en el servidor.

```bash
python manage.py makemigrations --merge <app>
# Confirmar con 'y'
python manage.py migrate
```

Si el merge falla con KeyError o errores de estado:
1. Eliminar la migración extra que no está en el repo
2. Eliminarla del registro de la BD: `DELETE FROM django_migrations WHERE name='0002_initial'`
3. Hacer `--fake` de las migraciones cuya estructura ya existe en la BD
4. Aplicar de verdad las que agregan columnas nuevas

---

### Ver qué columnas tiene una tabla en la BD
```bash
python manage.py dbshell
```
```sql
SELECT column_name FROM information_schema.columns
WHERE table_name='<nombre_tabla>'
ORDER BY ordinal_position;
\q
```

---

## Reiniciar Gunicorn manualmente
```bash
kill -HUP $(pgrep -f blmp_web_gunicorn)
```

---

## Checklist post-deploy
- [ ] `python manage.py showmigrations` — sin migraciones pendientes
- [ ] `tail -20 /var/log/blmp/gunicorn_web_error.log` — sin errores nuevos
- [ ] https://blmp.unl.edu.ec/ — carga correctamente
- [ ] Login funciona
