import argparse, json
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from db.config import get_engine
from db.models import LimiarConfig

SEED = Path(__file__).resolve().parents[1] / "data" / "seeds" / "limiares_semente.json"

def seed(engine, sobrescrever: bool = False) -> int:
    linhas = json.loads(SEED.read_text())
    with Session(engine) as s:
        n = 0
        for l in linhas:
            ex = s.execute(select(LimiarConfig).where(
                LimiarConfig.tipo_veiculo == l["tipo_veiculo"],
                LimiarConfig.tipo_manutencao == l["tipo_manutencao"],
            )).scalar_one_or_none()
            if ex is None:
                s.add(LimiarConfig(**l)); n += 1
            elif sobrescrever:
                for k, v in l.items(): setattr(ex, k, v)
                if s.is_modified(ex): n += 1

        s.commit()
    return n

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description=(
            "Semeia limiar_config a partir de data/seeds/limiares_semente.json "
            "(fonte única). Upsert por (tipo_veiculo, tipo_manutencao): insere "
            "ausentes e preserva valores existentes. Par SEM linha na tabela é "
            "'não-avaliável' para o motor — nunca há default silencioso."
        )
    )
    ap.add_argument("--sobrescrever", action="store_true", help="adota os valores do JSON, descartando edições locais (recalibração)")
    args = ap.parse_args()
    
    print(f"seed: {seed(get_engine(), sobrescrever=args.sobrescrever)} linhas afetadas "
          f"(sobrescrever={args.sobrescrever})")