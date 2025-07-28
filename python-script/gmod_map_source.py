import sys
from pathlib import Path


class Color:
    BLUE = "\033[0;36m"
    GREEN = "\033[0;32m"
    RED = "\033[0;31m"
    RESET = "\033[0m"
    YELLOW = "\033[1;33m"


class vstr(str):
    def replace_input(self, old: str, new: str) -> "vstr":
        return vstr(self.replace(f'"{old}"', f'"{new}"'))

    def replace_output(self, old: str, new: str) -> "vstr":
        return vstr(self.replace(f"{chr(27)}{old}{chr(27)}", f"{chr(27)}{new}{chr(27)}"))


def replace(target: Path):
    if target.suffix != ".vmf":
        print(f"{Color.RED}[ERROR]{Color.RESET} '{target.name}' is not a VMF file", file=sys.stderr)
        sys.exit(1)

    try:
        content: vstr = vstr(target.read_text().lower())
        #######################
        #    Generic Input    #
        #######################
        content = content.replace_input("onbeginsequence", "OnBeginSequence")
        content = content.replace_input("onbreak", "OnBreak")
        content = content.replace_input("oncase01", "OnCase01")
        content = content.replace_input("oncase02", "OnCase02")
        content = content.replace_input("oncase03", "OnCase03")
        content = content.replace_input("oncase04", "OnCase04")
        content = content.replace_input("oncase05", "OnCase05")
        content = content.replace_input("oncase06", "OnCase06")
        content = content.replace_input("oncase07", "OnCase07")
        content = content.replace_input("oncase08", "OnCase08")
        content = content.replace_input("oncase09", "OnCase09")
        content = content.replace_input("oncase10", "OnCase10")
        content = content.replace_input("oncase11", "OnCase11")
        content = content.replace_input("oncase12", "OnCase12")
        content = content.replace_input("oncase13", "OnCase13")
        content = content.replace_input("oncase14", "OnCase14")
        content = content.replace_input("oncase15", "OnCase15")
        content = content.replace_input("oncase16", "OnCase16")
        content = content.replace_input("oncompletion", "OnCompletion")
        content = content.replace_input("onendsequence", "OnEndSequence")
        content = content.replace_input("onendtouch", "OnEndTouch")
        content = content.replace_input("onentityspawned", "OnEntitySpawned")
        content = content.replace_input("onfalse", "OnFalse")
        content = content.replace_input("onhealthchanged", "OnHealthChanged")
        content = content.replace_input("onhitmax", "OnHitMax")
        content = content.replace_input("onmapspawn", "OnMapSpawn")
        content = content.replace_input("onnpcstartedusing", "OnNPCStartedUsing")
        content = content.replace_input("onnpcstoppedusing", "OnNPCStoppedUsing")
        content = content.replace_input("onopen", "OnOpen")
        content = content.replace_input("onpass", "OnPass")
        content = content.replace_input("onplayeruse", "OnPlayerUse")
        content = content.replace_input("onpressed", "OnPressed")
        content = content.replace_input("onspawnnpc", "OnSpawnNPC")
        content = content.replace_input("onstart", "OnStart")
        content = content.replace_input("onstarttouch", "OnStartTouch")
        content = content.replace_input("ontimer", "OnTimer")
        content = content.replace_input("ontimerhigh", "OnTimerHigh")
        content = content.replace_input("ontimerlow", "OnTimerLow")
        content = content.replace_input("ontrigger", "OnTrigger")
        content = content.replace_input("ontrigger1", "OnTrigger1")
        content = content.replace_input("ontrue", "OnTrue")
        content = content.replace_input("onuselocked", "OnUseLocked")
        content = content.replace_input("onuser1", "OnUser1")
        ########################
        #    Generic Output    #
        ########################
        content = content.replace_output("activate", "Activate")
        content = content.replace_output("add", "Add")
        content = content.replace_output("addcontext", "AddContext")
        content = content.replace_output("beginsequence", "BeginSequence")
        content = content.replace_output("cancel", "Cancel")
        content = content.replace_output("close", "Close")
        content = content.replace_output("color", "Color")
        content = content.replace_output("command", "Command")
        content = content.replace_output("disable", "Disable")
        content = content.replace_output("disablehint", "DisableHint")
        content = content.replace_output("display", "Display")
        content = content.replace_output("enable", "Enable")
        content = content.replace_output("enablehint", "EnableHint")
        content = content.replace_output("enablemotion", "EnableMotion")
        content = content.replace_output("explode", "Explode")
        content = content.replace_output("fade", "Fade")
        content = content.replace_output("forcenpctoactbusy", "ForceNPCToActBusy")
        content = content.replace_output("forcespawn", "ForceSpawn")
        content = content.replace_output("forcethisnpctoleave", "ForceThisNPCToLeave")
        content = content.replace_output("hidesprite", "HideSprite")
        content = content.replace_output("kill", "Kill")
        content = content.replace_output("open", "Open")
        content = content.replace_output("pause", "Pause")
        content = content.replace_output("pickrandom", "PickRandom")
        content = content.replace_output("playsound", "PlaySound")
        content = content.replace_output("resume", "Resume")
        content = content.replace_output("rollcredits", "RollCredits")
        content = content.replace_output("setautoexposuremax", "SetAutoExposureMax")
        content = content.replace_output("setautoexposuremin", "SetAutoExposureMin")
        content = content.replace_output("setbloomscale", "SetBloomScale")
        content = content.replace_output("setvalue", "SetValue")
        content = content.replace_output("showsprite", "ShowSprite")
        content = content.replace_output("skin", "Skin")
        content = content.replace_output("spawn", "Spawn")
        content = content.replace_output("start", "Start")
        content = content.replace_output("startfire", "StartFire")
        content = content.replace_output("startforward", "StartForward")
        content = content.replace_output("stop", "Stop")
        content = content.replace_output("stopsound", "StopSound")
        content = content.replace_output("subtract", "Subtract")
        content = content.replace_output("test", "Test")
        content = content.replace_output("toggle", "Toggle")
        content = content.replace_output("togglesprite", "ToggleSprite")
        content = content.replace_output("trigger", "Trigger")
        content = content.replace_output("turnoff", "TurnOff")
        content = content.replace_output("turnon", "TurnOn")
        content = content.replace_output("unlock", "Unlock")
        #######################
        #    Custom Entity    #
        #######################
        # Get A Life - env_textgal
        content = content.replace_input("env_textgal", "game_text")
        content = content.replace_output("displaytext", "Display")
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
