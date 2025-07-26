from pathlib import Path
import sys


class Color:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"

def replace(target: Path):
    if target.suffix != ".vmf":
        print(f"{Color.RED}[ERROR]{Color.RESET} '{target.name}' is not a VMF file", file=sys.stderr)

    try:
        content = target.read_text()
        content = content.lower()
        # Input
        content = content.replace('"oncompletion"', '"OnCompletion"')
        content = content.replace('"onendsequence"', '"OnEndSequence"')
        content = content.replace('"onendtouch"', '"OnEndTouch"')
        content = content.replace('"onentityspawned"', '"OnEntitySpawned"')
        content = content.replace('"onmapspawn"', '"OnMapSpawn"')
        content = content.replace('"onnpcstartedusing"', '"OnNPCStartedUsing"')
        content = content.replace('"onnpcstoppedusing"', '"OnNPCStoppedUsing"')
        content = content.replace('"onopen"', '"OnOpen"')
        content = content.replace('"onpass"', '"OnPass"')
        content = content.replace('"onplayeruse"', '"OnPlayerUse"')
        content = content.replace('"onpressed"', '"OnPressed"')
        content = content.replace('"onspawnnpc"', '"OnSpawnNPC"')
        content = content.replace('"onstarttouch"', '"OnStartTouch"')
        content = content.replace('"ontimer"', '"OnTimer"')
        content = content.replace('"ontimerhigh"', '"OnTimerHigh"')
        content = content.replace('"ontimerlow"', '"OnTimerLow"')
        content = content.replace('"ontrigger"', '"OnTrigger"')
        content = content.replace('"ontrigger1"', '"OnTrigger1"')
        content = content.replace('"onuser1"', '"OnUser1"')
        # Output
        content = content.replace(f"{chr(27)}activate{chr(27)}", f"{chr(27)}Activate{chr(27)}")
        content = content.replace(f"{chr(27)}addcontext{chr(27)}", f"{chr(27)}AddContext{chr(27)}")
        content = content.replace(f"{chr(27)}beginsequence{chr(27)}", f"{chr(27)}BeginSequence{chr(27)}")
        content = content.replace(f"{chr(27)}cancel{chr(27)}", f"{chr(27)}Cancel{chr(27)}")
        content = content.replace(f"{chr(27)}command{chr(27)}", f"{chr(27)}Command{chr(27)}")
        content = content.replace(f"{chr(27)}disablehint{chr(27)}", f"{chr(27)}DisableHint{chr(27)}")
        content = content.replace(f"{chr(27)}display{chr(27)}", f"{chr(27)}Display{chr(27)}")
        content = content.replace(f"{chr(27)}enable{chr(27)}", f"{chr(27)}Enable{chr(27)}")
        content = content.replace(f"{chr(27)}enablehint{chr(27)}", f"{chr(27)}EnableHint{chr(27)}")
        content = content.replace(f"{chr(27)}enablemotion{chr(27)}", f"{chr(27)}EnableMotion{chr(27)}")
        content = content.replace(f"{chr(27)}fade{chr(27)}", f"{chr(27)}Fade{chr(27)}")
        content = content.replace(f"{chr(27)}forcenpctoactbusy{chr(27)}", f"{chr(27)}ForceNPCToActBusy{chr(27)}")
        content = content.replace(f"{chr(27)}forcespawn{chr(27)}", f"{chr(27)}ForceSpawn{chr(27)}")
        content = content.replace(f"{chr(27)}forcethisnpctoleave{chr(27)}", f"{chr(27)}ForceThisNPCToLeave{chr(27)}")
        content = content.replace(f"{chr(27)}hidesprite{chr(27)}", f"{chr(27)}HideSprite{chr(27)}")
        content = content.replace(f"{chr(27)}kill{chr(27)}", f"{chr(27)}Kill{chr(27)}")
        content = content.replace(f"{chr(27)}pause{chr(27)}", f"{chr(27)}Pause{chr(27)}")
        content = content.replace(f"{chr(27)}playsound{chr(27)}", f"{chr(27)}PlaySound{chr(27)}")
        content = content.replace(f"{chr(27)}resume{chr(27)}", f"{chr(27)}Resume{chr(27)}")
        content = content.replace(f"{chr(27)}rollcredits{chr(27)}", f"{chr(27)}RollCredits{chr(27)}")
        content = content.replace(f"{chr(27)}setautoexposuremax{chr(27)}", f"{chr(27)}SetAutoExposureMax{chr(27)}")
        content = content.replace(f"{chr(27)}setautoexposuremin{chr(27)}", f"{chr(27)}SetAutoExposureMin{chr(27)}")
        content = content.replace(f"{chr(27)}setbloomscale{chr(27)}", f"{chr(27)}SetBloomScale{chr(27)}")
        content = content.replace(f"{chr(27)}spawn{chr(27)}", f"{chr(27)}Spawn{chr(27)}")
        content = content.replace(f"{chr(27)}start{chr(27)}", f"{chr(27)}Start{chr(27)}")
        content = content.replace(f"{chr(27)}startfire{chr(27)}", f"{chr(27)}StartFire{chr(27)}")
        content = content.replace(f"{chr(27)}startforward{chr(27)}", f"{chr(27)}StartForward{chr(27)}")
        content = content.replace(f"{chr(27)}stop{chr(27)}", f"{chr(27)}Stop{chr(27)}")
        content = content.replace(f"{chr(27)}stopsound{chr(27)}", f"{chr(27)}StopSound{chr(27)}")
        content = content.replace(f"{chr(27)}toggle{chr(27)}", f"{chr(27)}Toggle{chr(27)}")
        content = content.replace(f"{chr(27)}togglesprite{chr(27)}", f"{chr(27)}ToggleSprite{chr(27)}")
        content = content.replace(f"{chr(27)}trigger{chr(27)}", f"{chr(27)}Trigger{chr(27)}")
        content = content.replace(f"{chr(27)}turnoff{chr(27)}", f"{chr(27)}TurnOff{chr(27)}")
        content = content.replace(f"{chr(27)}turnon{chr(27)}", f"{chr(27)}TurnOn{chr(27)}")
        content = content.replace(f"{chr(27)}unlock{chr(27)}", f"{chr(27)}Unlock{chr(27)}")
        #
        target.write_text(content)
    except Exception as e:
        print(f"{Color.RED}[ERROR]{Color.RESET} Failed to process '{target}': {e}")

##########
#  MAIN  #
##########
def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    if target.is_file() and target.suffix == ".vmf":
        print(f"{Color.GREEN}[INFO ]{Color.RESET} Processing '{target.name}'")
        replace(target)
    elif target.is_dir():
        for src in target.glob("*.vmf"):
            print(f"{Color.GREEN}[INFO ]{Color.RESET} Processing '{src.name}'")
            replace(src)
    else:
        print(f"{Color.RED}[ERROR]{Color.RESET} There is no file to process", file=sys.stderr)

if __name__ == "__main__":
    main()
