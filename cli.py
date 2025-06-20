import argparse
import subprocess

def run_install():
    subprocess.run(["bash", "install.sh"])

def run_uninstall():
    subprocess.run(["bash", "uninstall.sh"])

def show_status():
    subprocess.run(["systemctl", "status", "tg2bale.service"])

def restart_service():
    subprocess.run(["systemctl", "restart", "tg2bale.service"])

def stop_service():
    subprocess.run(["systemctl", "stop", "tg2bale.service"])

def main():
    parser = argparse.ArgumentParser(
        description="Teltobale CLI Tool - Manage your Telegram to Bale forwarder"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("install", help="Run the installer script")
    subparsers.add_parser("uninstall", help="Run the uninstaller script")
    subparsers.add_parser("status", help="Check systemd service status")
    subparsers.add_parser("restart", help="Restart the bot service")
    subparsers.add_parser("stop", help="Stop the bot service")

    args = parser.parse_args()

    if args.command == "install":
        run_install()
    elif args.command == "uninstall":
        run_uninstall()
    elif args.command == "status":
        show_status()
    elif args.command == "restart":
        restart_service()
    elif args.command == "stop":
        stop_service()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
