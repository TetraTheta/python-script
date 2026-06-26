#!/usr/bin/env python3
"""
소스 엔진 맵의 소스 코드에 있는 불필요한 대문자를 제거한다
모든 문자를 소문자로 변환한 후, 핵심적인 요소만 다시 CamelCase로 변환한다
"""

import itertools
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from library.console import ConsoleColor, format_status
from library.text_file import read_text_with_fallback, write_text

INPUT_GENERIC = [
    ("onallspawneddead", "OnAllSpawnedDead"),
    ("onarrival", "OnArrival"),
    ("onawakened", "OnAwakened"),
    ("onballgrabbed", "OnBallGrabbed"),
    ("onballreinserted", "OnBallReInserted"),
    ("onbeginfade", "OnBeginFade"),
    ("onbeginsequence", "OnBeginSequence"),
    ("onbreak", "OnBreak"),
    ("oncase01", "OnCase01"),
    ("oncase02", "OnCase02"),
    ("oncase03", "OnCase03"),
    ("oncase04", "OnCase04"),
    ("oncase05", "OnCase05"),
    ("oncase06", "OnCase06"),
    ("oncase07", "OnCase07"),
    ("oncase08", "OnCase08"),
    ("oncase09", "OnCase09"),
    ("oncase10", "OnCase10"),
    ("oncase11", "OnCase11"),
    ("oncase12", "OnCase12"),
    ("oncase13", "OnCase13"),
    ("oncase14", "OnCase14"),
    ("oncase15", "OnCase15"),
    ("oncase16", "OnCase16"),
    ("onclose", "OnClose"),
    ("oncompletion", "OnCompletion"),
    ("ondamaged", "OnDamaged"),
    ("ondamagedbyplayer", "OnDamagedByPlayer"),
    ("ondeath", "OnDeath"),
    ("ondeploy", "OnDeploy"),
    ("onendsequence", "OnEndSequence"),
    ("onendtouch", "OnEndTouch"),
    ("onentityspawned", "OnEntitySpawned"),
    ("onfalse", "OnFalse"),
    ("onfire", "OnFire"),
    ("onfoundplayer", "OnFoundPlayer"),
    ("onfullyclosed", "OnFullyClosed"),
    ("onfullyopen", "OnFullyOpen"),
    ("ongotcontroller", "OnGotController"),
    ("ongotplayercontroller", "OnGotPlayerController"),
    ("onhealthchanged", "OnHealthChanged"),
    ("onhitmax", "OnHitMax"),
    ("onlostcontroller", "OnLostController"),
    ("onlostplayercontroller", "OnLostPlayerController"),
    ("onmapspawn", "OnMapSpawn"),
    ("onnpcstartedusing", "OnNPCStartedUsing"),
    ("onnpcstoppedusing", "OnNPCStoppedUsing"),
    ("onopen", "OnOpen"),
    ("onpass", "OnPass"),
    ("onphysgundrop", "OnPhysGunDrop"),
    ("onphysgunpickup", "OnPhysGunPickup"),
    ("onplayerpickup", "OnPlayerPickup"),
    ("onplayeruse", "OnPlayerUse"),
    ("onpressed", "OnPressed"),
    ("onshotdown", "OnShotDown"),
    ("onspawn", "OnSpawn"),
    ("onspawnnpc", "OnSpawnNPC"),
    ("onstart", "OnStart"),
    ("onstarttouch", "OnStartTouch"),
    ("onsurfacechangedtotarget", "OnSurfaceChangedToTarget"),
    ("ontimer", "OnTimer"),
    ("ontimerhigh", "OnTimerHigh"),
    ("ontimerlow", "OnTimerLow"),
    ("ontipped", "OnTipped"),
    ("ontouchedbyentity", "OnTouchedByEntity"),
    ("ontouching", "OnTouching"),
    ("ontrigger", "OnTrigger"),
    ("ontrigger1", "OnTrigger1"),
    ("ontrue", "OnTrue"),
    ("onuselocked", "OnUseLocked"),
    ("onuser1", "OnUser1"),
    ("onuser2", "OnUser2"),
    ("onuser3", "OnUser3"),
    ("onuser4", "OnUser4"),
]
INPUT_MOD = [("env_textgal", "game_text")]
OUTPUT_GENERIC = [
    ("activate", "Activate"),
    ("add", "Add"),
    ("addcontext", "AddContext"),
    ("addoutput", "AddOutput"),
    ("applyrelationship", "ApplyRelationship"),
    ("beginassault", "BeginAssault"),
    ("beginsequence", "BeginSequence"),
    ("break", "Break"),
    ("cancel", "Cancel"),
    ("cancelpending", "CancelPending"),
    ("cancelsequence", "CancelSequence"),
    ("choosenearestpathpoint", "ChooseNearestPathPoint"),
    ("clearparent", "ClearParent"),
    ("close", "Close"),
    ("color", "Color"),
    ("command", "Command"),
    ("disable", "Disable"),
    ("disablehint", "DisableHint"),
    ("disablemotion", "DisableMotion"),
    ("disablepath", "DisablePath"),
    ("display", "Display"),
    ("dissolve", "Dissolve"),
    ("dophysicsblast", "DoPhysicsBlast"),
    ("enable", "Enable"),
    ("enablehint", "EnableHint"),
    ("enablemotion", "EnableMotion"),
    ("explode", "Explode"),
    ("fade", "Fade"),
    ("fadeout", "FadeOut"),
    ("firetimer", "FireTimer"),
    ("flyaway", "FlyAway"),
    ("flytopathtrack", "FlyToPathTrack"),
    ("flytospecifictrackviapath", "FlyToSpecificTrackViaPath"),
    ("forcedrop", "ForceDrop"),
    ("forcenpctoactbusy", "ForceNPCToActBusy"),
    ("forcespawn", "ForceSpawn"),
    ("forcethisnpctoleave", "ForceThisNPCToLeave"),
    ("forgetentity", "ForgetEntity"),
    ("hidesprite", "HideSprite"),
    ("kill", "Kill"),
    ("killhierarchy", "KillHierarchy"),
    ("lightoff", "LightOff"),
    ("lighton", "LightOn"),
    ("lock", "Lock"),
    ("open", "Open"),
    ("pause", "Pause"),
    ("pickrandom", "PickRandom"),
    ("playsound", "PlaySound"),
    ("reload", "Reload"),
    ("resume", "Resume"),
    ("rollcredits", "RollCredits"),
    ("save", "Save"),
    ("selfdestruct", "SelfDestruct"),
    ("setanimation", "SetAnimation"),
    ("setautoexposuremax", "SetAutoExposureMax"),
    ("setautoexposuremin", "SetAutoExposureMin"),
    ("setbloomscale", "SetBloomScale"),
    ("setcolorlerpto", "SetColorLerpTo"),
    ("setdefaultanimation", "SetDefaultAnimation"),
    ("setenddistlerpto", "SetEndDistLerpTo"),
    ("sethealth", "SetHealth"),
    ("sethealthfraction", "SetHealthFraction"),
    ("setparentattachment", "SetParentAttachment"),
    ("setspeed", "SetSpeed"),
    ("setstartdistlerpto", "SetStartDistLerpTo"),
    ("setvalue", "SetValue"),
    ("showsprite", "ShowSprite"),
    ("skin", "Skin"),
    ("sparkonce", "SparkOnce"),
    ("spawn", "Spawn"),
    ("start", "Start"),
    ("startbreakablemovement", "StartBreakableMovement"),
    ("startdischarge", "StartDischarge"),
    ("startfire", "StartFire"),
    ("startfogtransition", "StartFogTransition"),
    ("startforward", "StartForward"),
    ("startpatrol", "StartPatrol"),
    ("startschedule", "StartSchedule"),
    ("startshake", "StartShake"),
    ("startspark", "StartSpark"),
    ("starttouch", "StartTouch"),
    ("stop", "Stop"),
    ("stopsound", "StopSound"),
    ("stopsweeping", "StopSweeping"),
    ("strikeonce", "StrikeOnce"),
    ("stripweaponsandsuit", "StripWeaponsAndSuit"),
    ("subtract", "Subtract"),
    ("sweepgrouprandomly", "SweepGroupRandomly"),
    ("sweepgrouprandomly", "SweepGroupRandomly"),
    ("teleport", "Teleport"),
    ("test", "Test"),
    ("toggle", "Toggle"),
    ("togglesound", "ToggleSound"),
    ("togglespark", "ToggleSpark"),
    ("togglesprite", "ToggleSprite"),
    ("trigger", "Trigger"),
    ("turnoff", "TurnOff"),
    ("turnon", "TurnOn"),
    ("unlock", "Unlock"),
    ("wake", "Wake"),
]
OUTPUT_MOD = [("displaytext", "Display")]
ENTITY_MOD = [("env_textgal", "game_text")]

# 단순 iteration만 필요하므로, 메모리 효율을 위해 itertools.chain을 사용함
INPUTS = itertools.chain(INPUT_GENERIC, INPUT_MOD, ENTITY_MOD)
OUTPUTS = itertools.chain(OUTPUT_GENERIC, OUTPUT_MOD)


class GmodMapSourceArgs(Namespace):
    target: Path | str


def parse_args() -> GmodMapSourceArgs:
    parser = ArgumentParser(description="Normalize Source Engine VMF entity input/output casing.")
    parser.add_argument("target", nargs="?", default=str(Path.cwd()), help="VMF file or directory")
    return parser.parse_args(namespace=GmodMapSourceArgs())


def main() -> None:
    args = parse_args()
    target = Path(args.target)

    if target.is_file() and target.suffix == ".vmf":
        print(format_status("INFO", ConsoleColor.GREEN, f"Processing '{target.name}'"))
        normalize_vmf_entities(target)
    elif target.is_dir():
        for source in target.glob("*.vmf"):
            print(format_status("INFO", ConsoleColor.GREEN, f"Processing '{source.name}'"))
            normalize_vmf_entities(source)
    else:
        print(format_status("ERROR", ConsoleColor.RED, "There is no file to process"), file=sys.stderr)


def normalize_vmf_entities(target: Path) -> None:
    if target.suffix != ".vmf":
        print(format_status("ERROR", ConsoleColor.RED, f"'{target.name}' is not a VMF file"), file=sys.stderr)
        sys.exit(1)

    try:
        content = read_text_with_fallback(target).lower()
        # VMF 소문자 -> CamelCase 변환
        for old, new in INPUTS:
            content = content.replace(f'"{old}"', f'"{new}"')
        separator = chr(27)  # ESC
        for old, new in OUTPUTS:
            content = content.replace(f"{separator}{old}{separator}", f"{separator}{new}{separator}")
        write_text(target, content)
    except OSError as error:
        print(format_status("ERROR", ConsoleColor.RED, f"Failed to process '{target}': {error}"))


if __name__ == "__main__":
    main()
