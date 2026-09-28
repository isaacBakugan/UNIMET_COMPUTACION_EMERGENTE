import csv
import os
import subprocess

# Rutas relativas al directorio padre (porque el script estará en la carpeta 'tareas')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(BASE_DIR, ".repos-trimestre-2627-1", "invitations-2627-1.csv")
REPOS_DIR = os.path.join(BASE_DIR, ".repos-trimestre-2627-1")
BASE_URL = "https://github.com/isaacBakugan/"

# Fecha de entrega de la Tarea 1
DEADLINE = "2026-09-27 23:59:59"

def main():
    if not os.path.exists(REPOS_DIR):
        os.makedirs(REPOS_DIR)

    repos = set()
    try:
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Repo'):
                    repos.add(row['Repo'])
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo {CSV_PATH}")
        return

    print(f"Encontrados {len(repos)} repositorios únicos en el CSV.")

    for repo in sorted(repos):
        print(f"\n" + "="*40)
        print(f"--- Analizando: {repo} ---")
        repo_path = os.path.join(REPOS_DIR, repo)
        
        # Clonar o actualizar (fetch + reset)
        repo_url = f"{BASE_URL}{repo}.git"
        if not os.path.exists(repo_path):
            print(f"Clonando {repo}...")
            res = subprocess.run(["git", "clone", repo_url, repo_path], capture_output=True, text=True)
            if res.returncode != 0:
                print(f"Error al clonar:\n{res.stderr}")
                continue
        else:
            print(f"Actualizando {repo} (fetch + reset)...")
            subprocess.run(["git", "-C", repo_path, "remote", "set-url", "origin", repo_url], capture_output=True)
            res = subprocess.run(["git", "-C", repo_path, "fetch", "origin"], capture_output=True, text=True)
            if res.returncode != 0:
                print(f"Error al hacer fetch:\n{res.stderr}")
                continue
            
            # Forzamos un reset --hard a la rama principal remota (main o master)
            res2 = subprocess.run(["git", "-C", repo_path, "reset", "--hard", "origin/main"], capture_output=True, text=True)
            if res2.returncode != 0:
                res3 = subprocess.run(["git", "-C", repo_path, "reset", "--hard", "origin/master"], capture_output=True, text=True)
                if res3.returncode != 0:
                    print(f"Error al hacer reset:\n{res2.stderr}\n{res3.stderr}")
                    continue

        # Verificar si hay cambios y fechas
        res_commits = subprocess.run(["git", "-C", repo_path, "rev-list", "--count", "HEAD"], capture_output=True, text=True)
        commit_count = int(res_commits.stdout.strip()) if res_commits.returncode == 0 and res_commits.stdout.strip().isdigit() else 0
        
        # Contar commits ANTES de la entrega
        res_before = subprocess.run(["git", "-C", repo_path, "rev-list", "--count", f"--before={DEADLINE}", "HEAD"], capture_output=True, text=True)
        commits_before = int(res_before.stdout.strip()) if res_before.returncode == 0 and res_before.stdout.strip().isdigit() else 0

        # Contar commits DESPUÉS de la entrega
        res_after = subprocess.run(["git", "-C", repo_path, "rev-list", "--count", f"--after={DEADLINE}", "HEAD"], capture_output=True, text=True)
        commits_after = int(res_after.stdout.strip()) if res_after.returncode == 0 and res_after.stdout.strip().isdigit() else 0

        res_first_commit = subprocess.run(["git", "-C", repo_path, "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True)
        first_commit = res_first_commit.stdout.strip().split('\n')[-1] if res_first_commit.returncode == 0 and res_first_commit.stdout.strip() else ""

        print(f"Commits totales en la rama principal: {commit_count}")
        print(f"  - A tiempo (antes o el {DEADLINE}): {commits_before}")
        if commits_after > 0:
            print(f"  - \033[91mTardíos (después del {DEADLINE}): {commits_after}\033[0m")
        else:
            print(f"  - Tardíos (después del {DEADLINE}): {commits_after}")
        
        if first_commit:
            res_diff = subprocess.run(["git", "-C", repo_path, "diff", f"{first_commit}..HEAD", "--stat"], capture_output=True, text=True)
            diff_stat = res_diff.stdout.strip()
        else:
            diff_stat = ""

        if commit_count > 1:
            print("ESTADO: [YES] TIENE CAMBIOS")
            if diff_stat:
                print("Resumen de cambios desde el template:")
                print(diff_stat)
            else:
                print("No hay diferencias en los archivos, pero hay más commits (posiblemente un merge vacío).")
        else:
            print("ESTADO: [NO] PARECE ESTAR SOLO EL TEMPLATE (1 commit)")

if __name__ == "__main__":
    main()
