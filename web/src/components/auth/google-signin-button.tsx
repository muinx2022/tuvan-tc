"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { getGoogleOauthPublicConfig } from "@/lib/api";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (options: {
            client_id: string;
            callback: (response: { credential?: string }) => void;
          }) => void;
          renderButton: (
            element: HTMLElement,
            options: Record<string, string | number>,
          ) => void;
        };
      };
    };
  }
}

type GoogleSignInButtonProps = {
  onCredential: (credential: string) => Promise<void>;
};

export function GoogleSignInButton({ onCredential }: GoogleSignInButtonProps) {
  const buttonRef = useRef<HTMLDivElement | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [clientId, setClientId] = useState(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "");
  const [configLoading, setConfigLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const config = await getGoogleOauthPublicConfig();
        if (!active) {
          return;
        }
        if (config.enabled && config.clientId) {
          setClientId(config.clientId);
        } else {
          setClientId("");
        }
      } catch {
        if (active) {
          setClientId(process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "");
        }
      } finally {
        if (active) {
          setConfigLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!ready || !clientId || !buttonRef.current || !window.google) {
      return;
    }

    buttonRef.current.innerHTML = "";
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: async (response) => {
        if (!response.credential || busy) {
          return;
        }
        setBusy(true);
        try {
          await onCredential(response.credential);
        } finally {
          setBusy(false);
        }
      },
    });
    window.google.accounts.id.renderButton(buttonRef.current, {
      type: "standard",
      theme: "outline",
      size: "large",
      width: 320,
      text: "continue_with",
      shape: "pill",
    });
  }, [busy, clientId, onCredential, ready]);

  return (
    <>
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onLoad={() => setReady(true)}
      />
      {configLoading ? (
        <button type="button" className="ghost-button" disabled>
          Dang tai cau hinh Google...
        </button>
      ) : clientId ? (
        <div className="google-button-wrap">
          <div ref={buttonRef} />
        </div>
      ) : (
        <button type="button" className="ghost-button" disabled>
          Google sign-in chua duoc cau hinh
        </button>
      )}
    </>
  );
}
