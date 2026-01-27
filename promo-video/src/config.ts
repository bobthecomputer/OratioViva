import promoConfigJson from '../promo.config.json';

export type Feature = {
  title: string;
  body: string;
};

export type PromoConfig = {
  brand: {
    name: string;
    tagline: string;
    url: string;
  };
  features: Feature[];
  assets: {
    logo: string;
    screenshots: string[];
    banners: string[];
    videos?: string[];
  };
  audio: {
    voiceover: string | null;
  };
  video: {
    format: 'landscape' | 'portrait';
    durationSeconds: number;
    fps: number;
    width: number;
    height: number;
  };
};

export const promoConfig = promoConfigJson as PromoConfig;
