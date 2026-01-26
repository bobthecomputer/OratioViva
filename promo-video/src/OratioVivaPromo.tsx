import React, {useMemo} from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {promoConfig} from './config';

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

const fade = (frame: number, inStart: number, inDur: number, outStart: number, outDur: number) => {
  const fin = clamp01((frame - inStart) / Math.max(1, inDur));
  const fout = 1 - clamp01((frame - outStart) / Math.max(1, outDur));
  return fin * fout;
};

const Title: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => {
  return (
    <div
      style={{
        fontFamily: 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial',
        letterSpacing: 0.2,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

const Sub: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => {
  return (
    <div
      style={{
        fontFamily: 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial',
        opacity: 0.9,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

const Pill: React.FC<{children: React.ReactNode; style?: React.CSSProperties}> = ({children, style}) => (
  <div
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 8,
      padding: '10px 14px',
      borderRadius: 999,
      background: 'rgba(15, 10, 6, 0.35)',
      border: '1px solid rgba(245, 232, 205, 0.18)',
      backdropFilter: 'blur(10px)',
      WebkitBackdropFilter: 'blur(10px)',
      ...style,
    }}
  >
    {children}
  </div>
);

const IconAtom: React.FC<{size?: number}> = ({size = 18}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{opacity: 0.9}}>
    <path
      d="M12 2c-1.9 0-3.8 1.2-5.3 3.4-1.4 2-2.3 4.6-2.3 6.6 0 2.7 1.1 5.3 2.9 7.3 1.2 1.3 2.8 2.3 4.7 2.3s3.5-1 4.7-2.3c1.8-2 2.9-4.6 2.9-7.3 0-2-.9-4.6-2.3-6.6C15.8 3.2 13.9 2 12 2Z"
      fill="none"
      stroke="rgba(245,232,205,0.9)"
      strokeWidth="1.2"
    />
    <circle cx="12" cy="12" r="1.6" fill="rgba(245,232,205,0.9)" />
    <path
      d="M3.3 9.5c2.8 1.7 6.3 2.7 8.7 2.7s5.9-1 8.7-2.7"
      fill="none"
      stroke="rgba(245,232,205,0.55)"
      strokeWidth="1.1"
    />
    <path
      d="M6.2 4.8c1.2 3 3.8 6 5.8 7.2 2 1.2 5.7 1.8 9 1.2"
      fill="none"
      stroke="rgba(245,232,205,0.35)"
      strokeWidth="1.0"
    />
  </svg>
);

const IconDNA: React.FC<{size?: number}> = ({size = 18}) => (
  <svg width={size} height={size} viewBox="0 0 24 24" style={{opacity: 0.9}}>
    <path
      d="M7 3c0 5 10 5 10 10s-10 5-10 10"
      fill="none"
      stroke="rgba(245,232,205,0.9)"
      strokeWidth="1.2"
    />
    <path
      d="M17 3c0 5-10 5-10 10s10 5 10 10"
      fill="none"
      stroke="rgba(245,232,205,0.55)"
      strokeWidth="1.1"
    />
    <path d="M8 7h8" stroke="rgba(245,232,205,0.4)" strokeWidth="1.1" />
    <path d="M8 12h8" stroke="rgba(245,232,205,0.4)" strokeWidth="1.1" />
    <path d="M8 17h8" stroke="rgba(245,232,205,0.4)" strokeWidth="1.1" />
  </svg>
);

const DeviceFrame: React.FC<{src?: string; label?: string}> = ({src, label}) => {
  return (
    <div
      style={{
        width: 980,
        height: 560,
        borderRadius: 28,
        background: 'rgba(10, 6, 4, 0.55)',
        border: '1px solid rgba(245,232,205,0.18)',
        boxShadow: '0 30px 80px rgba(0,0,0,0.45)',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 14,
          left: 18,
          right: 18,
          height: 26,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          opacity: 0.85,
        }}
      >
        <div style={{display: 'flex', gap: 8}}>
          <div style={{width: 10, height: 10, borderRadius: 999, background: 'rgba(245,232,205,0.35)'}} />
          <div style={{width: 10, height: 10, borderRadius: 999, background: 'rgba(245,232,205,0.22)'}} />
          <div style={{width: 10, height: 10, borderRadius: 999, background: 'rgba(245,232,205,0.15)'}} />
        </div>
        <div style={{fontSize: 12, color: 'rgba(245,232,205,0.75)'}}>{label ?? ''}</div>
        <div style={{width: 36}} />
      </div>

      {src ? (
        <Img
          src={staticFile(src)}
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: 'translateY(18px) scale(1.01)',
            filter: 'saturate(1.05) contrast(1.02)',
          }}
        />
      ) : (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            paddingTop: 58,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <div
            style={{
              width: '88%',
              height: '78%',
              borderRadius: 18,
              border: '1px dashed rgba(245,232,205,0.28)',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 18,
              padding: 22,
              opacity: 0.95,
            }}
          >
            <div style={{borderRadius: 14, background: 'rgba(245,232,205,0.08)'}} />
            <div style={{borderRadius: 14, background: 'rgba(245,232,205,0.08)'}} />
            <div style={{borderRadius: 14, background: 'rgba(245,232,205,0.08)'}} />
            <div style={{borderRadius: 14, background: 'rgba(245,232,205,0.08)'}} />
          </div>
          <div
            style={{
              position: 'absolute',
              bottom: 34,
              fontSize: 14,
              color: 'rgba(245,232,205,0.65)',
            }}
          >
            Add screenshots to replace this placeholder
          </div>
        </div>
      )}
    </div>
  );
};

const WaveBars: React.FC<{opacity?: number}> = ({opacity = 1}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();

  const bars = 72;
  const seed = 1337;

  const heights = useMemo(() => {
    const out: number[] = [];
    for (let i = 0; i < bars; i++) {
      // Deterministic pseudo-random base per bar.
      const r = Math.sin((i + seed) * 999) * 0.5 + 0.5;
      out.push(r);
    }
    return out;
  }, []);

  const t = frame / fps;

  return (
    <div
      style={{
        width: Math.min(1100, width * 0.72),
        height: 170,
        display: 'flex',
        gap: 6,
        alignItems: 'flex-end',
        opacity,
      }}
    >
      {heights.map((r, i) => {
        const wobble = 0.55 + 0.45 * Math.sin(t * 6.2 + i * 0.42);
        const amp = 22 + r * 86 * wobble;
        return (
          <div
            key={i}
            style={{
              width: 10,
              height: Math.max(10, amp),
              borderRadius: 999,
              background: 'rgba(245,232,205,0.55)',
              boxShadow: '0 8px 20px rgba(0,0,0,0.35)',
            }}
          />
        );
      })}
    </div>
  );
};

const FeatureCard: React.FC<{
  title: string;
  body: string;
  icon: 'atom' | 'dna' | 'spark';
  index: number;
  inFrame: number;
}> = ({title, body, icon, index, inFrame}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const local = frame - inFrame - index * 10;
  const appear = clamp01(local / 18);
  const s = spring({
    fps,
    frame: local,
    config: {damping: 18, mass: 0.8, stiffness: 120},
  });

  const y = interpolate(appear, [0, 1], [18, 0]);
  const o = appear;

  return (
    <div
      style={{
        width: 420,
        borderRadius: 22,
        padding: '18px 18px',
        background: 'rgba(10, 6, 4, 0.55)',
        border: '1px solid rgba(245,232,205,0.16)',
        boxShadow: '0 22px 60px rgba(0,0,0,0.35)',
        transform: `translateY(${y}px) scale(${0.98 + 0.02 * s})`,
        opacity: o,
      }}
    >
      <div style={{display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10}}>
        <div
          style={{
            width: 34,
            height: 34,
            borderRadius: 12,
            background: 'rgba(245,232,205,0.10)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon === 'atom' ? <IconAtom /> : icon === 'dna' ? <IconDNA /> : <IconAtom />}
        </div>
        <Title style={{fontSize: 20, color: 'rgba(245,232,205,0.95)', fontWeight: 650}}>{title}</Title>
      </div>
      <Sub style={{fontSize: 16, lineHeight: 1.35, color: 'rgba(245,232,205,0.78)'}}>{body}</Sub>
    </div>
  );
};

const Background: React.FC<{logoPath: string; intensity?: number}> = ({logoPath, intensity = 1}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();

  const glow = 0.35 + 0.10 * Math.sin(frame / 18);
  const vignette = `radial-gradient(ellipse at center, rgba(0,0,0,0) 0%, rgba(0,0,0,0.60) 72%, rgba(0,0,0,0.86) 100%)`;
  const drift = interpolate(frame, [0, durationInFrames], [0.0, 1.0]);

  return (
    <AbsoluteFill style={{backgroundColor: '#140E08'}}>
      <Img
        src={staticFile(logoPath)}
        style={{
          position: 'absolute',
          inset: -80,
          width: 'calc(100% + 160px)',
          height: 'calc(100% + 160px)',
          objectFit: 'cover',
          filter: `blur(22px) saturate(0.95) contrast(1.04)`,
          opacity: 0.92 * intensity,
          transform: `scale(${1.05 + 0.02 * drift}) translateY(${8 * drift}px)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at 40% 35%, rgba(245,232,205,${0.14 * glow}) 0%, rgba(245,232,205,0) 55%)`,
          mixBlendMode: 'screen',
        }}
      />
      <AbsoluteFill style={{background: vignette}} />
    </AbsoluteFill>
  );
};

export const OratioVivaPromo: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const logoPath = promoConfig.assets.logo || 'assets/logo.png';
  const voiceover = promoConfig.audio.voiceover;

  const introStart = 0;
  const introDur = Math.round(3 * fps);

  const featuresStart = introStart + introDur;
  const featuresDur = Math.round(5 * fps);

  const demoStart = featuresStart + featuresDur;
  const demoDur = Math.round(6 * fps);

  const audioStart = demoStart + demoDur;
  const audioDur = Math.round(4 * fps);

  const outroStart = audioStart + audioDur;
  const outroDur = Math.round(2 * fps);

  const brandIn = fade(frame, introStart, 18, outroStart + outroDur - 18, 18);

  return (
    <AbsoluteFill>
      <Background logoPath={logoPath} intensity={1} />

      {voiceover ? <Audio src={staticFile(voiceover)} /> : null}

      {/* Intro */}
      <Sequence from={introStart} durationInFrames={introDur}>
        <IntroScene opacity={brandIn} />
      </Sequence>

      {/* Features */}
      <Sequence from={featuresStart} durationInFrames={featuresDur}>
        <FeaturesScene />
      </Sequence>

      {/* Demo / Screens */}
      <Sequence from={demoStart} durationInFrames={demoDur}>
        <DemoScene />
      </Sequence>

      {/* Audio proof */}
      <Sequence from={audioStart} durationInFrames={audioDur}>
        <AudioScene />
      </Sequence>

      {/* Outro */}
      <Sequence from={outroStart} durationInFrames={outroDur}>
        <OutroScene />
      </Sequence>
    </AbsoluteFill>
  );
};

const IntroScene: React.FC<{opacity: number}> = ({opacity}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const s = spring({fps, frame, config: {damping: 16, mass: 0.9, stiffness: 110}});
  const o = clamp01(frame / 18);

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: opacity * o}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
        <div
          style={{
            width: 520,
            height: 520,
            borderRadius: 40,
            overflow: 'hidden',
            boxShadow: '0 32px 90px rgba(0,0,0,0.55)',
            border: '1px solid rgba(245,232,205,0.22)',
            transform: `scale(${0.92 + 0.08 * s})`,
          }}
        >
          <Img src={staticFile(promoConfig.assets.logo)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </div>

        <Title style={{fontSize: 62, color: 'rgba(245,232,205,0.95)', fontWeight: 750}}>
          {promoConfig.brand.name}
        </Title>
        <Sub style={{fontSize: 24, color: 'rgba(245,232,205,0.78)'}}>{promoConfig.brand.tagline}</Sub>
      </div>
    </AbsoluteFill>
  );
};

const FeaturesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const o = fade(frame, 0, 16, Math.round(5 * fps) - 16, 16);
  const banners = promoConfig.assets.banners ?? [];

  const features = promoConfig.features?.slice(0, 3) ?? [];
  const filled = [...features];
  while (filled.length < 3) {
    filled.push({title: 'Fast workflow', body: 'Drop your notes in, get clean narration out.'});
  }

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
      {banners.length ? (
        <Img
          src={staticFile(banners[0])}
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            filter: 'blur(18px) saturate(1.05) contrast(1.05)',
            opacity: 0.28,
            transform: 'scale(1.08)',
          }}
        />
      ) : null}
      <div style={{width: 1500, display: 'flex', flexDirection: 'column', gap: 22}}>
        <Pill>
          <IconAtom />
          <Title style={{fontSize: 18, color: 'rgba(245,232,205,0.88)', fontWeight: 650}}>
            Built for science-first study
          </Title>
        </Pill>

        <div style={{display: 'flex', gap: 24, justifyContent: 'center'}}>
          <FeatureCard title={filled[0].title} body={filled[0].body} icon="atom" index={0} inFrame={0} />
          <FeatureCard title={filled[1].title} body={filled[1].body} icon="dna" index={1} inFrame={0} />
          <FeatureCard title={filled[2].title} body={filled[2].body} icon="spark" index={2} inFrame={0} />
        </div>

        <Sub style={{textAlign: 'center', fontSize: 18, color: 'rgba(245,232,205,0.66)'}}>
          Use your own voice, or pick a style preset. Export audio for lectures, videos, and revision.
        </Sub>
      </div>
    </AbsoluteFill>
  );
};

const DemoScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const o = fade(frame, 0, 16, Math.round(6 * fps) - 16, 16);

  const screenshots = (promoConfig.assets.screenshots && promoConfig.assets.screenshots.length)
    ? promoConfig.assets.screenshots
    : (promoConfig.assets.banners ?? []);
  const label = screenshots.length ? 'App preview' : 'Preview placeholder';

  const idx = screenshots.length >= 2 ? (frame < Math.round(3 * fps) ? 0 : 1) : 0;
  const nextIdx = screenshots.length >= 3 ? (frame < Math.round(2 * fps) ? 0 : frame < Math.round(4 * fps) ? 1 : 2) : idx;

  const a = clamp01(frame / 18);
  const b = clamp01((frame - Math.round(3 * fps)) / 18);

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
        <Pill>
          <IconDNA />
          <Title style={{fontSize: 18, color: 'rgba(245,232,205,0.88)', fontWeight: 650}}>See it in action</Title>
        </Pill>

        <div style={{position: 'relative'}}>
          <div style={{position: 'absolute', inset: 0, transform: 'translate(18px, 18px)', opacity: 0.35}}>
            <DeviceFrame src={screenshots[nextIdx]} label={label} />
          </div>

          <div style={{opacity: 1}}>
            <div style={{opacity: 1 - b}}>
              <DeviceFrame src={screenshots[idx]} label={label} />
            </div>
            {screenshots.length >= 2 ? (
              <div style={{position: 'absolute', inset: 0, opacity: b}}>
                <DeviceFrame src={screenshots[nextIdx]} label={label} />
              </div>
            ) : null}
          </div>
        </div>

        <Sub style={{fontSize: 18, color: 'rgba(245,232,205,0.70)'}}>
          Paste content, choose a voice, export. Keep control over structure and tone.
        </Sub>
      </div>
    </AbsoluteFill>
  );
};

const AudioScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const o = fade(frame, 0, 16, Math.round(4 * fps) - 16, 16);
  const y = interpolate(clamp01(frame / 18), [0, 1], [14, 0]);

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, transform: `translateY(${y}px)`}}>
        <Pill>
          <IconAtom />
          <Title style={{fontSize: 18, color: 'rgba(245,232,205,0.88)', fontWeight: 650}}>Hear the clarity</Title>
        </Pill>
        <WaveBars opacity={0.95} />
        <Sub style={{fontSize: 18, color: 'rgba(245,232,205,0.72)'}}>
          Natural narration with pacing that matches technical material.
        </Sub>
      </div>
    </AbsoluteFill>
  );
};

const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const o = clamp01(frame / 18);
  const y = interpolate(o, [0, 1], [10, 0]);

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18, transform: `translateY(${y}px)`}}>
        <Title style={{fontSize: 54, color: 'rgba(245,232,205,0.95)', fontWeight: 760}}>
          {promoConfig.brand.name}
        </Title>
        <Sub style={{fontSize: 22, color: 'rgba(245,232,205,0.78)'}}>{promoConfig.brand.tagline}</Sub>
        <div
          style={{
            marginTop: 8,
            padding: '12px 18px',
            borderRadius: 999,
            border: '1px solid rgba(245,232,205,0.20)',
            background: 'rgba(10,6,4,0.55)',
            color: 'rgba(245,232,205,0.88)',
            fontSize: 20,
          }}
        >
          {promoConfig.brand.url}
        </div>
      </div>
    </AbsoluteFill>
  );
};
