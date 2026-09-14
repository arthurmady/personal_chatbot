const VALID_STATES = new Set(["idle","happy","thinking","surprised","sad","error","success","loading","sleeping","singing"]);

export const resolveState = (state) => VALID_STATES.has(state) ? state : 'idle';

export const preset = {
  "version": 2,
  "id": "wobbi-original",
  "slug": "wobbi",
  "name": "Wobbi",
  "componentName": "Wobbi",
  "preset": "wobbi",
  "shape": "egg",
  "eyes": "sleepy",
  "nose": "none",
  "brows": "none",
  "mouth": "smile",
  "depth": "deep",
  "color": "#7A9B6D",
  "mouthColor": "#111218",
  "noseColor": "#111218",
  "browColor": "#111218",
  "pupilColor": "#111218",
  "lashColor": "#111218",
  "eyeOutlineColor": "#111218",
  "eyeOutlineWidth": 0,
  "head": "none",
  "accessory": "none",
  "accessoryColor": "#262331",
  "accentColor": "#ffe49b",
  "eyeColor": "#ffffff",
  "outlineColor": "#ffffff",
  "outlineWidth": 5,
  "background": {
    "type": "transparent",
    "color": "#4222b2"
  },
  "size": 256,
  "defaultState": "idle",
  "reactions": {
    "idle": {
      "duration": 2400,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "blink",
          "enabled": true
        },
        {
          "type": "eye-movement",
          "enabled": true
        }
      ]
    },
    "happy": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "bounce",
          "enabled": true
        },
        {
          "type": "squash",
          "enabled": true
        },
        {
          "type": "tilt",
          "enabled": true
        },
        {
          "type": "blink",
          "enabled": true
        }
      ]
    },
    "thinking": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "tilt",
          "enabled": true
        },
        {
          "type": "eye-movement",
          "enabled": true
        }
      ]
    },
    "surprised": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "squash",
          "enabled": true
        },
        {
          "type": "blink",
          "enabled": true
        }
      ]
    },
    "sad": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "tilt",
          "enabled": true
        }
      ]
    },
    "error": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "shake",
          "enabled": true
        }
      ]
    },
    "success": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "bounce",
          "enabled": true
        },
        {
          "type": "squash",
          "enabled": true
        }
      ]
    },
    "loading": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "tilt",
          "enabled": true
        },
        {
          "type": "blink",
          "enabled": true
        }
      ]
    },
    "sleeping": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "blink",
          "enabled": true
        }
      ]
    },
    "singing": {
      "duration": 800,
      "intensity": 60,
      "easing": "ease-out",
      "playback": "loop",
      "movements": [
        {
          "type": "bounce",
          "enabled": true
        },
        {
          "type": "mouth",
          "enabled": true
        }
      ]
    }
  },
  "export": {
    "folder": "src/components/mascot",
    "framework": "react"
  },
  "accessibility": {
    "respectReducedMotion": true,
    "pauseOffscreen": true,
    "label": "Mascotte Wobbi"
  }
};
