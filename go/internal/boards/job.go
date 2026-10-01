package boards

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
)

// Job is one posting, in the same shape whichever board it came from.
// The `json:"..."` tags tell Go what to call each field when it
// writes JSON — Go fields must start with a capital letter to be
// visible outside the package, but we want lowercase in the file.
type Job struct {
	Source      string `json:"source"`      // "greenhouse" or "lever"
	Company     string `json:"company"`     // board token or site name
	ExternalID  string `json:"external_id"` // the board's own id
	Title       string `json:"title"`
	Location    string `json:"location"`
	URL         string `json:"url"`
	Description string `json:"description"`
	Hash        string `json:"hash"` // fingerprint of the above
}

// Fingerprint returns a SHA-256 hash of the fields that decide
// whether this posting has really changed. If a board republishes
// the same posting with a new timestamp, the hash is unchanged
// and we skip it.
func (j *Job) Fingerprint() string {
	var b strings.Builder
	parts := []string{
		j.Source, j.Company, j.ExternalID,
		j.Title, j.Location, j.Description,
	}
	for _, p := range parts {
		b.WriteString(p)
		// A separator byte that cannot appear in the text, so
		// "Senior"+"Engineer" and "SeniorEng"+"ineer" hash
		// differently. This is deep dive 2 from section 3.
		b.WriteByte('\x1f')
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:])
}
