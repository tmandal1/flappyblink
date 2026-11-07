"""Portrait Flappy Bird presentation using the requested repository's sprites."""
import argparse
import math
import os
from pathlib import Path
import pygame
from .model import Game, W, H, FLOOR, BIRD_X, PIPE_WIDTH, GAP

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "sprites"
INK = (63, 43, 48)
PAPER = (244, 229, 174)


def viewport(size, width=W):
    scale = min(size[0]/width, size[1]/H)
    return pygame.Rect((size[0]-int(width*scale))//2, (size[1]-int(H*scale))//2,
                       max(1,int(width*scale)), max(1,int(H*scale)))


def main():
    parser = argparse.ArgumentParser(description="Blink Bird: classic portrait edition")
    parser.add_argument("--muse", action="store_true")
    parser.add_argument("--no-sidebar", action="store_true", help="Portrait game only")
    parser.add_argument("--stream-name")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--preview-state", choices=("ready","playing","settings","calibration","over"), default="ready")
    parser.add_argument("--screenshot", default="preview.png")
    args = parser.parse_args()
    if args.smoke_test:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    pygame.init()
    total_width = W if args.no_sidebar else W+220
    screen = pygame.display.set_mode((total_width*2,H*2), pygame.RESIZABLE)
    pygame.display.set_caption("Blink Bird | Classic")
    canvas = pygame.Surface((total_width,H))
    load = lambda name: pygame.image.load(str(ASSETS / (name+".png"))).convert_alpha()
    background, base, bird, pipe, welcome = [load(n) for n in ("background","base","bird","pipe","messages")]
    welcome.set_colorkey((255,255,255))
    top_pipe = pygame.transform.flip(pipe,False,True)
    digits = [load(str(i)) for i in range(10)]
    pygame.display.set_icon(bird)
    fonts = {n:pygame.font.Font(None,n) for n in (14,16,18,20,24,30)}
    game = Game()
    game.practice = True
    clock = pygame.time.Clock()
    muse, error = None, ""
    if args.muse:
        try:
            from .stream import MuseInput
            muse = MuseInput(args.stream_name)
        except ImportError as exc:
            error = "Install requirements-muse.txt. Keyboard still works."
            print(error,exc)
    panel = "calibration" if args.muse else None
    status = None
    buttons = []
    elapsed, frames = 0.,0
    if args.smoke_test:
        if args.preview_state == "playing":
            panel = None
            game.state = "playing"
            game.pipes = [[162.,180.,False],[342.,200.,False]]
            game.y,game.score = 130.,1
        elif args.preview_state == "over":
            game.state = "over"
        elif args.preview_state in ("settings","calibration"):
            panel = args.preview_state

    def text(value,x,y,size=18,color=INK,center=False):
        surf = fonts[size].render(str(value),True,color)
        canvas.blit(surf,surf.get_rect(midtop=(x,y)) if center else (x,y))

    def wrap(value,y,width=218,size=18):
        line = ""
        for word in str(value).split():
            trial = (line+" "+word).strip()
            if fonts[size].size(trial)[0]>width and line:
                text(line,35,y,size)
                y += size
                line=word
            else:
                line=trial
        text(line,35,y,size)
        return y+size

    def button(label,y,action,x=35,width=218):
        rect=pygame.Rect(x,y,width,25)
        pygame.draw.rect(canvas,INK,rect)
        pygame.draw.rect(canvas,(228,145,55),rect.inflate(-4,-4))
        text(label,rect.centerx,y+5,18,(255,255,237),True)
        buttons.append((rect,action))

    def act(name):
        nonlocal panel
        if name in ("settings","pause"):
            if panel:
                panel=None
                # Resume explicitly with Space, to avoid accidental flight.
            else:
                if game.state=="playing":
                    game.state="paused"
                panel="settings"
        elif name=="close":
            panel=None
        elif name=="flap":
            panel=None
            if game.state=="over":
                game.reset()
            if game.state=="paused":
                game.state="playing"
            game.flap("Keyboard / click")
        elif name=="restart":
            game.reset()
            panel=None
        elif name=="practice":
            game.practice=not game.practice
            game.reset()
        elif name=="calibrate":
            game.reset()
            panel="calibration"
            if muse:
                muse.recalibrate()
        elif name in ("more","less") and muse:
            muse.sensitivity(.85 if name=="more" else 1/.85)
        if muse:
            muse.flaps.clear()

    running=True
    try:
        while running:
            dt=min(clock.tick(60)/1000,.04)
            elapsed+=dt
            for e in pygame.event.get():
                if e.type==pygame.QUIT:
                    running=False
                elif e.type==pygame.WINDOWFOCUSLOST and game.state=="playing":
                    game.state="paused"
                elif e.type==pygame.KEYDOWN:
                    keys={pygame.K_SPACE:"flap",pygame.K_UP:"flap",pygame.K_b:"flap",
                          pygame.K_p:"pause",pygame.K_s:"settings",pygame.K_r:"restart",
                          pygame.K_t:"practice",pygame.K_c:"calibrate",
                          pygame.K_LEFTBRACKET:"more",pygame.K_RIGHTBRACKET:"less"}
                    if e.key==pygame.K_ESCAPE:
                        if panel:
                            act("close")
                        else:
                            running=False
                    elif e.key in keys:
                        act(keys[e.key])
                elif e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
                    view=viewport(screen.get_size(),total_width)
                    if view.collidepoint(e.pos):
                        pos=((e.pos[0]-view.x)*total_width/view.w,(e.pos[1]-view.y)*H/view.h)
                        for rect,name in buttons:
                            if rect.collidepoint(pos):
                                act(name)
                                break
                        else:
                            if panel is None and pos[0]<W and pos[1]<FLOOR:
                                act("flap")
            status=muse.snapshot() if muse else None
            if muse:
                blink=muse.flaps.poll()
                if blink and status["stage"]=="ready" and panel is None and game.state=="playing":
                    game.flap("Blink")
            if not args.smoke_test:
                game.update(dt)
            buttons.clear()
            canvas.blit(background,(0,0))
            canvas.set_clip((0,0,W,FLOOR))
            if game.state!="ready":
                for x,middle,_ in game.pipes:
                    canvas.blit(top_pipe,(round(x),round(middle-GAP/2)-320))
                    canvas.blit(pipe,(round(x),round(middle+GAP/2)))
            by=game.y+(math.sin(elapsed*4)*3 if game.state=="ready" else 0)
            canvas.blit(bird,bird.get_rect(center=(BIRD_X,round(by))))
            canvas.set_clip(None)
            offset=int(elapsed*65)%48 if game.state=="playing" else 0
            canvas.blit(base,(-offset,FLOOR))
            if game.state=="ready" and panel is None:
                canvas.blit(welcome,((W-welcome.get_width())//2,55))
                text("Blink control / Space / Tap",W//2,348,18,INK,True)
            elif panel is None:
                score=[digits[int(d)] for d in str(game.score)]
                x=(W-sum(d.get_width() for d in score))//2
                for digit in score:
                    canvas.blit(digit,(x,55))
                    x+=digit.get_width()
            if panel is None and game.state in ("paused","over"):
                pygame.draw.rect(canvas,INK,(28,169,232,128))
                pygame.draw.rect(canvas,PAPER,(31,172,226,122))
                text("PAUSED" if game.state=="paused" else "GAME OVER",W//2,186,30,INK,True)
                text(f"Score {game.score}    Best {game.best}",W//2,224,20,INK,True)
                button("Resume" if game.state=="paused" else "Try again",258,"flap")
            # Controls live on the sandy ground, outside the game area.
            text("PRACTICE" if game.practice else "CHALLENGE",W//2,438,16,INK,True)
            button("Settings / Calibration",460,"settings",45,198)
            if panel:
                pygame.draw.rect(canvas,INK,(22,44,244,355))
                pygame.draw.rect(canvas,PAPER,(25,47,238,349))
                title="CALIBRATION" if panel=="calibration" else "SETTINGS"
                text(title,W//2,61,24,INK,True)
                if panel=="calibration":
                    stage=status["stage"] if status else "keyboard"
                    text(stage.upper(),W//2,94,20,INK,True)
                    wrap(status["message"] if status else (error or
                         "Launch with --muse to connect. Keyboard play is available."),122)
                    progress=status["progress"] if status else 0
                    pygame.draw.rect(canvas,INK,(35,189,218,9))
                    pygame.draw.rect(canvas,(87,174,70),(37,191,int(214*progress),5))
                    if status:
                        text(f'Blinks: {status["count"]}  Threshold: {status["threshold"]:.1f}',35,208,16)
                        trace=status["trace"]
                        pygame.draw.rect(canvas,(255,246,205),(35,234,218,50))
                        scale=max(status["threshold"]*2,max(trace,default=0),20)
                        y=280-status["threshold"]/scale*42
                        pygame.draw.line(canvas,(213,139,42),(36,y),(251,y))
                        if len(trace)>1:
                            pygame.draw.lines(canvas,(36,117,68),False,
                                [(36+i*215/(len(trace)-1),280-v/scale*42) for i,v in enumerate(trace)],1)
                    button("More sensitive",294,"more",35,106)
                    button("Less sensitive",294,"less",147,106)
                    button("Start / continue with Space",331,"flap")
                    text("C recalibrate    Esc close",W//2,370,16,INK,True)
                else:
                    button("Resume / Start",101,"flap")
                    button("Restart",136,"restart")
                    button("Practice: ON" if game.practice else "Practice: OFF",171,"practice")
                    button("Calibrate headset",206,"calibrate")
                    button("More sensitive [",241,"more")
                    button("Less sensitive ]",276,"less")
                    wrap("Space / Up / Tap: flap. P: pause. R: retry. S: settings.",319,size=16)
                    text("Esc closes this menu",W//2,375,16,INK,True)
            if not args.no_sidebar:
                left=W+14
                pygame.draw.rect(canvas,(245,235,197),(W,0,220,H))
                pygame.draw.line(canvas,INK,(W,0),(W,H),2)
                text("LIVE EEG",left,18,24)
                text("Muse / frontal channels",left,44,16)
                stage=status["stage"] if status else "keyboard"
                text(stage.upper(),left,73,20)
                text("Last 3 seconds / 1-15 Hz",left,99,16)
                channels=status.get("trace_channels",[]) if status else []
                amplitude=max(25.,max((abs(v) for pair in channels for v in pair),default=0.))
                for index,label,color in ((0,"AF7",(35,128,114)),(1,"AF8",(121,79,168))):
                    top=131+index*110
                    text(label,left,top-18,18,color)
                    rect=pygame.Rect(left,top,192,82)
                    pygame.draw.rect(canvas,(255,250,228),rect)
                    for gy in (top+20,top+41,top+62):
                        pygame.draw.line(canvas,(217,210,183),(left,gy),(left+192,gy))
                    if len(channels)>1:
                        points=[(left+i*191/(len(channels)-1),top+41-pair[index]/amplitude*36)
                                for i,pair in enumerate(channels)]
                        pygame.draw.lines(canvas,color,False,points,1)
                    else:
                        text("Waiting for EEG",left+40,top+33,16)
                text(f"Scale +/-{amplitude:.0f} uV",left,329,16)
                count=status["count"] if status else 0
                threshold=status["threshold"] if status else 0
                text(f"Blinks: {count}",left,353,20)
                text(f"Threshold: {threshold:.1f} uV" if status else "Run with --muse to connect",left,379,16)
                button("More sensitive",404,"more",left,192)
                button("Less sensitive",436,"less",left,192)
                button("Calibrate / view status",468,"calibrate",left,192)
            view=viewport(screen.get_size(),total_width)
            screen.fill((24,24,24))
            # Nearest-neighbor scaling preserves the repository's pixel artwork.
            screen.blit(pygame.transform.scale(canvas,view.size),view)
            pygame.display.flip()
            frames+=1
            if args.smoke_test and frames>=3:
                pygame.image.save(pygame.transform.scale(canvas,(total_width*2,H*2)),args.screenshot)
                running=False
    finally:
        if muse:
            muse.close()
        pygame.quit()


if __name__=="__main__":
    main()
