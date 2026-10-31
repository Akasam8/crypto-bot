"""Clear a halt. Run by the Resume workflow (Actions tab) after you've reviewed why it halted."""
from .config import STATE_DIR
from .journal import load_state, save_state
from .notify import send


def main():
    p = STATE_DIR / "state.json"
    s = load_state(p)
    was = s.get("halt_reason", "")
    s.update(halted=False, halt_reason="", consecutive_errors=0)
    save_state(p, s)
    send(f"▶️ Bot resumed. It had been halted for: {was or 'nothing'}.")


if __name__ == "__main__":
    main()
