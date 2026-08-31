import type {CSSProperties, FC, ReactNode} from 'react';

export const COLORS = {
  navy: '#06142c',
  deepBlue: '#0b2d66',
  blue: '#246ff2',
  cyan: '#5ba7ff',
  mint: '#31c8a4',
  white: '#f8fbff',
  muted: '#aebbd0',
  ink: '#07162e',
} as const;

export const FONT_STACK =
  '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", Arial, sans-serif';

type TextProps = {
  children: ReactNode;
  style?: CSSProperties;
};

export const Eyebrow: FC<TextProps> = ({children, style}) => (
  <div
    style={{
      color: COLORS.mint,
      fontFamily: FONT_STACK,
      fontSize: 25,
      fontWeight: 800,
      letterSpacing: 4,
      textTransform: 'uppercase',
      ...style,
    }}
  >
    {children}
  </div>
);

export const Headline: FC<TextProps> = ({children, style}) => (
  <div
    style={{
      color: COLORS.white,
      fontFamily: FONT_STACK,
      fontSize: 94,
      fontWeight: 760,
      letterSpacing: -4,
      lineHeight: 0.98,
      ...style,
    }}
  >
    {children}
  </div>
);

export const BodyCopy: FC<TextProps> = ({children, style}) => (
  <div
    style={{
      color: COLORS.muted,
      fontFamily: FONT_STACK,
      fontSize: 36,
      fontWeight: 460,
      lineHeight: 1.32,
      ...style,
    }}
  >
    {children}
  </div>
);
