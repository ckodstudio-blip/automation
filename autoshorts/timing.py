"""Silence-assisted estimates, not speech recognition or exact forced alignment."""
import array
import bisect
import logging
import math
import sys
import wave


def read_audio(path):
    with wave.open(str(path), 'rb') as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 24000:
            raise ValueError('Timing expects mono PCM16 24000 Hz WAV')
        samples = array.array('h', wav.readframes(wav.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
    if not samples:
        raise ValueError('Empty audio')
    return samples


def analyze(path, scenes):
    """Find scene boundaries near estimated turn lengths, preferring silence.

    The full soundtrack is muxed unchanged; these boundaries only select the
    character/background/subtitle on screen. No words are removed or duplicated.
    """
    samples = read_audio(path)
    rate, hop = 24000, 480  # 20 ms envelope
    length = len(samples) / rate
    if not 1 < length <= 70:
        raise ValueError('Whole-story voice must be longer than 1 second and at most 70 seconds')
    if not scenes:
        raise ValueError('Empty story')
    envelope = [math.sqrt(sum(v*v for v in samples[i:i+hop]) / len(samples[i:i+hop]))
                for i in range(0, len(samples), hop)]
    peak = max(envelope, default=0)
    if peak < 100:
        raise ValueError('Generated story audio is silent or too quiet')
    threshold = max(100, peak * .025)
    pauses = []
    start = None
    for i, level in enumerate(envelope + [peak]):
        if level < threshold and start is None:
            start = i
        elif level >= threshold and start is not None:
            a, b = start*.02, min(i*.02, length)
            if b-a >= .18 and a > .1 and b < length-.1:
                pauses.append(((a+b)/2, b-a))
            start = None
    # Estimate by word count with a modest character component for longer words.
    weights = [max(1, len(s['narration'].split())) + len(s['narration'])/35 for s in scenes]
    total_weight = sum(weights)
    targets, accumulated = [], 0
    for weight in weights[:-1]:
        accumulated += weight
        targets.append(length*accumulated/total_weight)
    # Dynamic programming avoids greedy selection reusing a pause or creating
    # tiny scenes. Every output frame belongs to exactly one scene.
    min_span = min(.65, length/(len(scenes)*2))
    states = [(0., 0., [])]
    for index, target in enumerate(targets):
        remaining = len(targets)-index
        choices = [(p, gap, False) for p,gap in pauses
                   if abs(p-target) <= max(1.5, length*.12)]
        choices.append((target, 0., True))
        next_states = []
        for end,gap,estimated in choices:
            if length-end < remaining*min_span:
                continue
            best = None
            for previous,cost,path in states:
                if end-previous < min_span:
                    continue
                expected = length*weights[index]/total_weight
                score = cost + ((end-previous-expected)/max(expected,1))**2
                score += ((end-target)/max(length*.12,1))**2 * .2
                score += 1.5 if estimated else .08/max(gap,.18)
                candidate = (end,score,path+[(end,estimated)])
                if best is None or score < best[1]:
                    best = candidate
            if best:
                next_states.append(best)
        if not next_states:
            raise ValueError('Could not construct a valid story timeline')
        states = next_states
    best = min(states, key=lambda s:s[1]+((length-s[0]-length*weights[-1]/total_weight)/max(length*weights[-1]/total_weight,1))**2)
    boundaries = [0.] + [p for p,_ in best[2]] + [length]
    estimated = sum(flag for _,flag in best[2])
    logging.warning('Scene timing is approximate: %s/%s boundaries used word-length estimates; others use nearby silence.',
                    estimated, len(targets))
    # Use the original envelope for amplitude-based mouth animation.
    levels = [min(1,level/max(peak*.65,150)) if level>threshold else 0 for level in envelope]
    return boundaries, levels, .02


def scene_at(boundaries, time):
    return min(len(boundaries)-2, max(0,bisect.bisect_right(boundaries,time)-1))
