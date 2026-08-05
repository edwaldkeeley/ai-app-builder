"use client";

import { useState, useEffect } from "react";

/**
 * Detects whether the viewport is below the mobile breakpoint (768px).
 * Also auto-collapses the mobile sidebar on transition.
 */
export function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkWidth = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkWidth();
    window.addEventListener("resize", checkWidth);
    return () => window.removeEventListener("resize", checkWidth);
  }, []);

  return isMobile;
}
