from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from db.config import get_engine, get_url
from db.seed_limiares import seed

def main():
    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", str(get_url()))
    command.upgrade(cfg, "head")
    engine = get_engine()
    seed(engine)
    names = sorted(inspect(engine).get_table_names())
    
    # senha nunca vai para o console 
    url_segura = make_url(get_url()).render_as_string(hide_password=True)
    print(f"OK [{url_segura}] {len(names)} tabelas\n " + "\n ".join(names))

if __name__ == "__main__":
    main()
    