// app/layout.tsx
export const metadata = {
  title: 'Send2290',
  description: 'IRS Form 2290 E-Filing Portal',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
