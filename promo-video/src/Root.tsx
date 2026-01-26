import React from 'react';
import {Composition} from 'remotion';
import {promoConfig} from './config';
import {OratioVivaPromo} from './OratioVivaPromo';

export const RemotionRoot: React.FC = () => {
  const fps = promoConfig.video.fps ?? 30;
  const durationInFrames = Math.round((promoConfig.video.durationSeconds ?? 20) * fps);

  return (
    <>
      <Composition
        id="OratioVivaPromo"
        component={OratioVivaPromo}
        durationInFrames={durationInFrames}
        fps={fps}
        width={promoConfig.video.width ?? 1920}
        height={promoConfig.video.height ?? 1080}
        defaultProps={{}}
      />
      <Composition
        id="OratioVivaPromoPortrait"
        component={OratioVivaPromo}
        durationInFrames={durationInFrames}
        fps={fps}
        width={1080}
        height={1920}
        defaultProps={{}}
      />
    </>
  );
};
