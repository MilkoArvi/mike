"""Gestos con la cámara (MediaPipe Hands). Corre en un hilo aparte; emite eventos:
  'mano_abierta'  -> mostrar UI
  'puño'          -> ocultar UI
  'pinza'         -> (pulgar+índice juntos) activa modo mover: la UI gira siguiendo el ángulo de tu mano
  'giro:<grados>' -> ángulo de la mano mientras está en pinza (0-360)
"""
import math, threading, time


class Gestos:
    def __init__(self, cfg: dict, on_evento):
        self.cfg = cfg
        self.on_evento = on_evento  # (str) -> None, thread-safe
        self._parar = False

    def iniciar(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        import cv2, mediapipe as mp
        hands = mp.solutions.hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
        cap = cv2.VideoCapture(self.cfg.get("camara", 0))
        ultimo, ultimo_t = None, 0
        while not self._parar and cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.1)
                continue
            res = hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            gesto = None
            if res.multi_hand_landmarks:
                lm = res.multi_hand_landmarks[0].landmark
                puntas = [8, 12, 16, 20]
                extendidos = sum(1 for p in puntas if lm[p].y < lm[p - 2].y)
                pinza = math.dist((lm[4].x, lm[4].y), (lm[8].x, lm[8].y)) < 0.05
                if pinza:
                    ang = (math.degrees(math.atan2(lm[8].y - lm[0].y, lm[8].x - lm[0].x)) + 360) % 360
                    gesto = f"giro:{int(ang)}"
                elif extendidos >= 4:
                    gesto = "mano_abierta"
                elif extendidos == 0:
                    gesto = "puño"
            # anti-rebote: mismo gesto discreto no se repite en 1.5 s; el giro sí se envía continuo
            if gesto and (gesto.startswith("giro") or gesto != ultimo or time.time() - ultimo_t > 1.5):
                self.on_evento(gesto)
                ultimo, ultimo_t = gesto, time.time()
            time.sleep(0.05)
        cap.release()

    def detener(self):
        self._parar = True
