import React, {useMemo} from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  Video,
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

const isVideo = (src?: string) => !!src && /\.(mp4|mov|webm)$/i.test(src);

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

const Background: React.FC<{logoPath: string; intensity?: number}> = ({logoPath, intensity = 1}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();

  const glow = 0.35 + 0.1 * Math.sin(frame / 18);
  const vignette =
    'radial-gradient(ellipse at center, rgba(0,0,0,0) 0%, rgba(0,0,0,0.60) 72%, rgba(0,0,0,0.86) 100%)';
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
          filter: 'blur(22px) saturate(0.95) contrast(1.04)',
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

const WaveBars: React.FC<{opacity?: number; height?: number}> = ({opacity = 1, height = 170}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();

  const bars = 72;
  const seed = 1337;

  const heights = useMemo(() => {
    const out: number[] = [];
    for (let i = 0; i < bars; i++) {
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
        height,
        display: 'flex',
        gap: 6,
        alignItems: 'flex-end',
        opacity,
      }}
    >
      {heights.map((r, i) => {
        const wobble = 0.55 + 0.45 * Math.sin(t * 6.2 + i * 0.42);
        const amp = 18 + r * 90 * wobble;
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

const MediaFill: React.FC<{src?: string; startFrom?: number; dim?: number; style?: React.CSSProperties}> = ({
  src,
  startFrom = 0,
  dim = 0.25,
  style,
}) => {
  if (!src) return null;

  const commonStyle: React.CSSProperties = {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    filter: 'saturate(1.05) contrast(1.05)',
    ...style,
  };

  return (
    <AbsoluteFill>
      {isVideo(src) ? (
        <Video src={staticFile(src)} startFrom={startFrom} muted style={commonStyle} />
      ) : (
        <Img src={staticFile(src)} style={commonStyle} />
      )}
      <AbsoluteFill style={{background: `rgba(6, 4, 3, ${dim})`}} />
    </AbsoluteFill>
  );
};

const HookScene: React.FC<{videoSrc?: string}> = ({videoSrc}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const scale = interpolate(frame, [0, fps * 4], [1.05, 1.18]);
  const o = clamp01(frame / 16);

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center'}}>
      <MediaFill
        src={videoSrc}
        startFrom={fps}
        dim={0.35}
        style={{transform: `scale(${scale})`}}
      />
      <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
        <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
          <Pill>
            <IconAtom />
            <Title style={{fontSize: 18, color: 'rgba(245,232,205,0.88)', fontWeight: 650}}>
              Local TTS, studio-quality.
            </Title>
          </Pill>
          <Title style={{fontSize: 66, color: 'rgba(245,232,205,0.98)', fontWeight: 760, textAlign: 'center'}}>
            Make audio feel human.
          </Title>
          <div style={{transform: 'translateY(8px)'}}>
            <WaveBars opacity={0.45} height={120} />
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const ProblemScene: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const o = clamp01(frame / 16);
  const fadeCloud = clamp01(1 - frame / (fps * 2.2));

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 26}}>
        <Title style={{fontSize: 54, color: 'rgba(245,232,205,0.95)', fontWeight: 730}}>
          No cloud. No latency. No compromises.
        </Title>
        <div style={{display: 'flex', gap: 18}}>
          <div
            style={{
              width: 420,
              height: 200,
              borderRadius: 20,
              background: 'rgba(245,232,205,0.08)',
              border: '1px solid rgba(245,232,205,0.18)',
              position: 'relative',
              overflow: 'hidden',
              opacity: fadeCloud,
            }}
          >
            <AbsoluteFill style={{
              background: 'radial-gradient(circle at 30% 40%, rgba(245,232,205,0.35), rgba(245,232,205,0))',
              filter: 'blur(8px)',
            }} />
            <Title style={{fontSize: 22, color: 'rgba(245,232,205,0.85)', fontWeight: 650, position: 'absolute', bottom: 18, left: 20}}>
              Cloud
            </Title>
          </div>
          <div
            style={{
              width: 420,
              height: 200,
              borderRadius: 20,
              background: 'rgba(10, 6, 4, 0.6)',
              border: '1px solid rgba(245,232,205,0.26)',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <AbsoluteFill style={{
              background: 'linear-gradient(135deg, rgba(245,232,205,0.12), rgba(245,232,205,0))',
            }} />
            <Title style={{fontSize: 22, color: 'rgba(245,232,205,0.95)', fontWeight: 650, position: 'absolute', bottom: 18, left: 20}}>
              Local App
            </Title>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const FeatureRow: React.FC<{features: {title: string}[]; inFrame: number}> = ({features, inFrame}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  return (
    <div style={{display: 'flex', gap: 18}}>
      {features.map((feature, index) => {
        const local = frame - inFrame - index * 16;
        const appear = clamp01(local / 16);
        const y = interpolate(appear, [0, 1], [12, 0]);
        return (
          <div
            key={feature.title}
            style={{
              padding: '14px 18px',
              borderRadius: 999,
              border: '1px solid rgba(245,232,205,0.22)',
              background: 'rgba(10, 6, 4, 0.58)',
              opacity: appear,
              transform: `translateY(${y}px)`,
              boxShadow: '0 18px 40px rgba(0,0,0,0.35)',
            }}
          >
            <Title style={{fontSize: 20, color: 'rgba(245,232,205,0.92)', fontWeight: 650}}>{feature.title}</Title>
          </div>
        );
      })}
    </div>
  );
};

const CoreScene: React.FC<{videoSrc?: string}> = ({videoSrc}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const o = fade(frame, 0, 16, Math.round(10 * fps) - 16, 16);
  const scale = interpolate(frame, [0, fps * 10], [1.03, 1.08]);
  const features = promoConfig.features ?? [];

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
      <MediaFill src={videoSrc} startFrom={fps * 3} dim={0.4} style={{transform: `scale(${scale})`}} />
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22}}>
        <Pill>
          <IconDNA />
          <Title style={{fontSize: 18, color: 'rgba(245,232,205,0.88)', fontWeight: 650}}>Core value</Title>
        </Pill>
        <Title style={{fontSize: 50, color: 'rgba(245,232,205,0.98)', fontWeight: 720, textAlign: 'center'}}>
          Direct the voice. Shape the mood.
        </Title>
        <FeatureRow features={features.map((f) => ({title: f.title}))} inFrame={0} />
      </div>
    </AbsoluteFill>
  );
};

const ProofScene: React.FC<{videoSrc?: string}> = ({videoSrc}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();

  const o = fade(frame, 0, 16, Math.round(8 * fps) - 16, 16);
  const fill = clamp01((frame - 10) / (fps * 6));

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
      <MediaFill src={videoSrc} startFrom={fps * 6} dim={0.55} />
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20}}>
        <Pill>
          <IconAtom />
          <Title style={{fontSize: 18, color: 'rgba(245,232,205,0.88)', fontWeight: 650}}>
            Real-time playback + clean exports
          </Title>
        </Pill>
        <WaveBars opacity={0.9} />
        <div
          style={{
            width: Math.min(980, width * 0.7),
            height: 10,
            borderRadius: 999,
            background: 'rgba(245,232,205,0.18)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${Math.round(fill * 100)}%`,
              height: '100%',
              borderRadius: 999,
              background: 'linear-gradient(90deg, rgba(245,232,205,0.85), rgba(245,232,205,0.45))',
              boxShadow: '0 0 18px rgba(245,232,205,0.55)',
            }}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const CtaScene: React.FC<{logoPath: string}> = ({logoPath}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();

  const o = clamp01(frame / 16);
  const s = spring({fps, frame, config: {damping: 16, mass: 0.9, stiffness: 120}});

  return (
    <AbsoluteFill style={{alignItems: 'center', justifyContent: 'center', opacity: o}}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18}}>
        <div
          style={{
            width: 180,
            height: 180,
            borderRadius: 32,
            overflow: 'hidden',
            border: '1px solid rgba(245,232,205,0.25)',
            boxShadow: '0 24px 60px rgba(0,0,0,0.45)',
            transform: `scale(${0.92 + 0.08 * s})`,
          }}
        >
          <Img src={staticFile(logoPath)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
        </div>
        <Title style={{fontSize: 54, color: 'rgba(245,232,205,0.98)', fontWeight: 760, textAlign: 'center'}}>
          OratioViva Studio - Create the voice, your way.
        </Title>
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

export const OratioVivaPromo: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();

  const logoPath = promoConfig.assets.logo || 'assets/logo.png';
  const voiceover = promoConfig.audio.voiceover;
  const videos = promoConfig.assets.videos ?? [];
  const clipA = videos[0];
  const clipB = videos[1] ?? videos[0];

  const hookDur = Math.round(4 * fps);
  const problemDur = Math.round(4 * fps);
  const coreDur = Math.round(10 * fps);
  const proofDur = Math.round(8 * fps);
  const ctaDur = Math.max(1, durationInFrames - (hookDur + problemDur + coreDur + proofDur));

  const hookStart = 0;
  const problemStart = hookStart + hookDur;
  const coreStart = problemStart + problemDur;
  const proofStart = coreStart + coreDur;
  const ctaStart = proofStart + proofDur;

  const brandIn = fade(frame, hookStart, 18, ctaStart + ctaDur - 18, 18);

  return (
    <AbsoluteFill>
      <Background logoPath={logoPath} intensity={1} />

      {voiceover ? <Audio src={staticFile(voiceover)} /> : null}

      <Sequence from={hookStart} durationInFrames={hookDur}>
        <AbsoluteFill style={{opacity: brandIn}}>
          <HookScene videoSrc={clipA} />
        </AbsoluteFill>
      </Sequence>

      <Sequence from={problemStart} durationInFrames={problemDur}>
        <ProblemScene />
      </Sequence>

      <Sequence from={coreStart} durationInFrames={coreDur}>
        <CoreScene videoSrc={clipB} />
      </Sequence>

      <Sequence from={proofStart} durationInFrames={proofDur}>
        <ProofScene videoSrc={clipA} />
      </Sequence>

      <Sequence from={ctaStart} durationInFrames={ctaDur}>
        <CtaScene logoPath={logoPath} />
      </Sequence>
    </AbsoluteFill>
  );
};
