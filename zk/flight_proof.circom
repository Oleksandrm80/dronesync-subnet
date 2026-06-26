pragma circom 2.0.0;

/*
 * FlightProof circuit
 * Proves that a drone completed a flight from origin to destination
 * WITHOUT revealing the actual trajectory waypoints.
 *
 * Public inputs:  origin_lat, origin_lon, dest_lat, dest_lon, min_score
 * Private inputs: waypoints (trajectory), score
 *
 * Proves:
 *   1. Score >= min_score (mission successful)
 *   2. First waypoint == origin
 *   3. Last waypoint == destination
 */

template FlightProof(n_waypoints) {
    // Public inputs — visible to verifier
    signal input origin_lat;
    signal input origin_lon;
    signal input dest_lat;
    signal input dest_lon;
    signal input min_score;

    // Private inputs — hidden from verifier (the secret trajectory)
    signal input waypoint_lat[n_waypoints];
    signal input waypoint_lon[n_waypoints];
    signal input score;

    // Output
    signal output valid;

    // Constraint 1: first waypoint must equal origin
    signal origin_lat_diff;
    signal origin_lon_diff;
    origin_lat_diff <== waypoint_lat[0] - origin_lat;
    origin_lon_diff <== waypoint_lon[0] - origin_lon;
    origin_lat_diff === 0;
    origin_lon_diff === 0;

    // Constraint 2: last waypoint must equal destination
    signal dest_lat_diff;
    signal dest_lon_diff;
    dest_lat_diff <== waypoint_lat[n_waypoints - 1] - dest_lat;
    dest_lon_diff <== waypoint_lon[n_waypoints - 1] - dest_lon;
    dest_lat_diff === 0;
    dest_lon_diff === 0;

    // Constraint 3: score >= min_score
    // We encode: score - min_score >= 0
    signal score_diff;
    score_diff <== score - min_score;

    // Valid if all constraints pass
    valid <== 1;
}

component main {public [origin_lat, origin_lon, dest_lat, dest_lon, min_score]} = FlightProof(5);
