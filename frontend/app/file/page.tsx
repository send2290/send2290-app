"use client";
import { Suspense } from 'react';
import FilePageContent from './FilePageContent';

export default function FilePage() {
  return (
    <Suspense fallback={<div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>}>
      <FilePageContent />
    </Suspense>
  );
}
