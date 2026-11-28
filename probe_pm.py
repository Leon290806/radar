import sys, os
sys.path[:0]=["smart","."]
os.environ.pop("RADAR_PASSWORT", None)
import wetter as W
S={}
W.lauf(S, [])
