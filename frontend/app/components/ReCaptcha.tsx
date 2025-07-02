"use client";
import { forwardRef, useImperativeHandle, useRef } from 'react';
import ReCAPTCHA from 'react-google-recaptcha';

export interface ReCaptchaRef {
  getValue: () => string | null;
  reset: () => void;
  execute: () => void;
}

interface ReCaptchaProps {
  sitekey: string;
  theme?: 'light' | 'dark';
  size?: 'compact' | 'normal';
  onChange?: (token: string | null) => void;
  onExpired?: () => void;
  onError?: () => void;
}

const ReCaptchaComponent = forwardRef<ReCaptchaRef, ReCaptchaProps>(
  ({ sitekey, theme = 'light', size = 'normal', onChange, onExpired, onError }, ref) => {
    const recaptchaRef = useRef<ReCAPTCHA>(null);

    useImperativeHandle(ref, () => ({
      getValue: () => {
        return recaptchaRef.current?.getValue() || null;
      },
      reset: () => {
        recaptchaRef.current?.reset();
      },
      execute: () => {
        recaptchaRef.current?.execute();
      }
    }));

    return (
      <div style={{ margin: '10px 0' }}>
        <ReCAPTCHA
          ref={recaptchaRef}
          sitekey={sitekey}
          theme={theme}
          size={size}
          onChange={onChange}
          onExpired={onExpired}
          onError={onError}
        />
      </div>
    );
  }
);

ReCaptchaComponent.displayName = 'ReCaptchaComponent';

export default ReCaptchaComponent;
