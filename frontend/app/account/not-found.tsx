/**
 * NOT FOUND PAGE
 * Shows when account routes are not found
 */
export default function NotFound() {
  return (
    <div style={{ 
      padding: 40, 
      fontFamily: "Segoe UI, sans-serif",
      textAlign: "center",
      maxWidth: 600,
      margin: "0 auto"
    }}>
      <h2 style={{ color: "#d32f2f", marginBottom: 16 }}>Page Not Found</h2>
      <p style={{ color: "#666", marginBottom: 24 }}>
        The account page you're looking for doesn't exist.
      </p>
      <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
        <a 
          href="/account"
          style={{
            display: "inline-block",
            padding: "10px 20px",
            backgroundColor: "#1565c0",
            color: "white",
            textDecoration: "none",
            borderRadius: 4
          }}
        >
          Go to Account Dashboard
        </a>
        <a 
          href="/"
          style={{
            display: "inline-block",
            padding: "10px 20px",
            backgroundColor: "#6c757d",
            color: "white",
            textDecoration: "none",
            borderRadius: 4
          }}
        >
          Go to Home
        </a>
      </div>
    </div>
  );
}
