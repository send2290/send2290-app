/**
 * LOADING PAGE
 * Shows while the account page is loading
 */
export default function Loading() {
  return (
    <div style={{ 
      padding: 40, 
      fontFamily: "Segoe UI, sans-serif",
      textAlign: "center",
      maxWidth: 600,
      margin: "0 auto"
    }}>
      <h2 style={{ color: "#1565c0", marginBottom: 16 }}>Loading Account...</h2>
      <p style={{ color: "#666" }}>Please wait while we load your account information.</p>
    </div>
  );
}
