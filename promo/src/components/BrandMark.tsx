import type {FC} from 'react';
import {COLORS} from './Typography';

export const BrandMark: FC<{size?: number}> = ({size = 96}) => (
  <svg width={size} height={size} viewBox="0 0 100 112" aria-label="Paycheck Guardian shield">
    <defs>
      <linearGradient id="shield-gradient" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#55e0c0" />
        <stop offset="1" stopColor={COLORS.mint} />
      </linearGradient>
    </defs>
    <path d="M50 3 94 20v31c0 28-16 47-44 58C22 98 6 79 6 51V20L50 3Z" fill="url(#shield-gradient)" />
    <path d="M50 16v77c18-10 28-24 28-43V31L50 20v-4Z" fill={COLORS.white} opacity="0.94" />
  </svg>
);
