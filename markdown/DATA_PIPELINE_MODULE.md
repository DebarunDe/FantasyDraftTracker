# Data Pipeline Module Design - UPDATED FOR REAL DATA

## Overview

The Data Pipeline module transforms FantasyPros CSV exports into structured JSON format with calculated VOR values. This module processes **actual 2025 season data** organized across multiple position-specific files.

## Actual Data Structure (2025 Season)

### Input Files

**1. Rankings File**: `FantasyPros_2025_Draft_ALL_Rankings.csv`
- Contains: Overall rankings, position ranks, ADP, bye weeks, tiers
- Columns: `RK`, `TIERS`, `PLAYER NAME`, `TEAM`, `POS`, `BYE WEEK`, `SOS SEASON`, `ECR VS. ADP`
- Position Format: `WR1`, `RB2`, `QB1`, `TE1` (includes rank)

**2. QB Projections**: `FantasyPros_Fantasy_Football_Projections_QB.csv`
- Columns: `Player`, `Team`, Passing stats (`ATT`, `CMP`, `YDS`, `TDS`, `INTS`), Rushing stats (`ATT`, `YDS`, `TDS`), `FL`, `FPTS`
- Note: Has duplicate column names (ATT and YDS appear twice)

**3. FLEX Projections**: `FantasyPros_Fantasy_Football_Projections_FLX.csv`
- Contains: RB, WR, TE projections combined
- Columns: `Player`, `Team`, `POS`, Rushing stats (`ATT`, `YDS`, `TDS`), Receiving stats (`REC`, `YDS`, `TDS`), `FL`, `FPTS`
- Position Format: `RB1`, `WR5`, etc. (includes rank)

**4. K Projections**: `FantasyPros_Fantasy_Football_Projections_K.csv`
- Columns: `Player`, `Team`, `FG`, `FGA`, `XPT`, `FPTS`

**5. DST Projections**: `FantasyPros_Fantasy_Football_Projections_DST.csv`
- Columns: `Player`, `Team`, `SACK`, `INT`, `FR`, `FF`, `TD`, `SAFETY`, `PA`, `YDS_AGN`, `FPTS`
- Player = Team name (e.g., "Philadelphia Eagles")

## Key Insights from Real Data

1. **Position ranks embedded in POS column**: `WR1`, `RB23` (not just `WR`, `RB`)
2. **Duplicate column names**: QB file has two `ATT` columns (passing, rushing), two `YDS` columns
3. **All projections include FPTS**: Pre-calculated fantasy points (appears to be PPR-based)
4. **FLEX file combines RB/WR/TE**: One file for all flex-eligible positions
5. **Rankings file has position-specific ranks**: Need to extract base position from `POS` column
6. **Bye weeks in rankings**: Not in projection files
7. **Team names vary**: Some use city (Philadelphia Eagles), some use abbreviation (PHI)

## Updated Pipeline Architecture

```
Input Files (5 CSVs)
    ↓
[Ingestion Layer]
    - Read each CSV with position-aware parsing
    - Handle duplicate column names (QB)
    - Extract position from rank format (WR1 → WR)
    ↓
[Cleaning Layer]
    - Standardize team names (PHI vs Philadelphia Eagles)
    - Extract base position from POS column
    - Handle quoted values and formatting
    - Merge player data across files
    ↓
[Transformation Layer]
    - Combine projections from all files
    - Merge with rankings data (by player name)
    - Calculate scoring format variants (Standard, Half PPR, Full PPR)
    - Generate unique player IDs
    ↓
[VOR Calculation Layer]
    - Calculate baseline VOR for each position
    - Use provided FPTS as PPR baseline
    - Calculate Standard and Half PPR variants
    ↓
[Output Layer]
    - Generate structured JSON
    - Include all stats and projections
    - Store by season/year
```

## Module Structure

```
src/data_pipeline/
├── __init__.py
├── ingestion.py              # CSV reading with position-aware logic
├── cleaning.py               # Team name standardization, position extraction
├── transformation.py         # Merge files, calculate scoring variants
├── vor_calculation.py        # Position-specific VOR
├── loader.py                 # JSON output
├── config.py                 # Column mappings, scoring systems
├── models.py                 # Data classes
└── run_update.py             # Main execution script
```

## Component Details

### 1. Ingestion (`ingestion.py`)

**Purpose**: Read FantasyPros CSVs handling their specific quirks

```python
class FantasyProsIngester:
    """Handles FantasyPros-specific CSV reading"""
    
    def __init__(self, data_dir: Path, year: int):
        self.data_dir = data_dir
        self.year = year
        
    def read_rankings(self) -> pd.DataFrame:
        """
        Read rankings file.
        
        Expected filename: FantasyPros_{year}_Draft_ALL_Rankings.csv
        Handles quoted values, extracts all columns
        """
        filepath = self.data_dir / f"FantasyPros_{self.year}_Draft_ALL_Rankings.csv"
        
        # Read with quote handling
        df = pd.read_csv(filepath, quotechar='"')
        
        # Remove quotes from values
        df = df.applymap(lambda x: x.strip('"') if isinstance(x, str) else x)
        
        return df
        
    def read_qb_projections(self) -> pd.DataFrame:
        """
        Read QB projections with duplicate column handling.
        
        Columns: Player, Team, ATT(pass), CMP, YDS(pass), TDS(pass), INTS,
                 ATT(rush), YDS(rush), TDS(rush), FL, FPTS
        """
        filepath = self.data_dir / f"FantasyPros_Fantasy_Football_Projections_QB.csv"
        
        # Read with custom column names to avoid duplicates
        df = pd.read_csv(filepath, quotechar='"', skiprows=1)  # Skip header
        
        # Manually set column names
        df.columns = [
            'Player', 'Team', 
            'Pass_Att', 'Pass_Cmp', 'Pass_Yds', 'Pass_TD', 'Pass_Int',
            'Rush_Att', 'Rush_Yds', 'Rush_TD',
            'FL', 'FPTS'
        ]
        
        # Remove empty rows
        df = df[df['Player'].notna() & (df['Player'] != ' ')]
        
        return df
    
    def read_flex_projections(self) -> pd.DataFrame:
        """
        Read FLEX projections (RB/WR/TE combined).
        
        Contains position rank in POS column (e.g., RB1, WR23)
        """
        filepath = self.data_dir / f"FantasyPros_Fantasy_Football_Projections_FLX.csv"
        
        df = pd.read_csv(filepath, quotechar='"', skiprows=1)
        df.columns = [
            'Player', 'Team', 'POS',
            'Rush_Att', 'Rush_Yds', 'Rush_TD',
            'Rec', 'Rec_Yds', 'Rec_TD',
            'FL', 'FPTS'
        ]
        
        # Remove empty rows
        df = df[df['Player'].notna() & (df['Player'] != ' ')]
        
        return df
    
    def read_k_projections(self) -> pd.DataFrame:
        """Read kicker projections."""
        filepath = self.data_dir / f"FantasyPros_Fantasy_Football_Projections_K.csv"
        df = pd.read_csv(filepath, quotechar='"')
        return df[df['Player'].notna() & (df['Player'] != ' ')]
    
    def read_dst_projections(self) -> pd.DataFrame:
        """Read defense/special teams projections."""
        filepath = self.data_dir / f"FantasyPros_Fantasy_Football_Projections_DST.csv"
        df = pd.read_csv(filepath, quotechar='"')
        return df[df['Player'].notna() & (df['Player'] != ' ')]
```

### 2. Cleaning (`cleaning.py`)

**Purpose**: Standardize data across files

```python
class FantasyProsDataCleaner:
    """Cleans FantasyPros data"""
    
    def extract_base_position(self, pos_str: str) -> str:
        """
        Extract base position from rank format.
        
        Examples:
            WR1 → WR
            RB23 → RB
            QB1 → QB
            TE2 → TE
        """
        if pd.isna(pos_str):
            return None
        
        # Extract letters only (position)
        position = ''.join([c for c in str(pos_str) if c.isalpha()])
        
        # Standardize
        position_map = {
            'WR': 'WR',
            'RB': 'RB',
            'QB': 'QB',
            'TE': 'TE',
            'K': 'K',
            'PK': 'K',  # Some sources use PK
            'DST': 'DST',
            'DEF': 'DST'
        }
        
        return position_map.get(position, position)
    
    def extract_position_rank(self, pos_str: str) -> Optional[int]:
        """
        Extract numeric rank from position.
        
        Examples:
            WR1 → 1
            RB23 → 23
        """
        if pd.isna(pos_str):
            return None
        
        # Extract numbers only
        rank = ''.join([c for c in str(pos_str) if c.isdigit()])
        
        return int(rank) if rank else None
    
    def standardize_team_names(self, team: str) -> str:
        """
        Standardize team abbreviations.
        
        Handles both:
            - Full names (Philadelphia Eagles → PHI)
            - Abbreviations (PHI → PHI)
        """
        if pd.isna(team) or team.strip() == '':
            return None
        
        # Full name to abbreviation mapping
        team_mapping = {
            'Philadelphia Eagles': 'PHI',
            'Denver Broncos': 'DEN',
            'Buffalo Bills': 'BUF',
            'Houston Texans': 'HOU',
            'Baltimore Ravens': 'BAL',
            'Green Bay Packers': 'GB',
            'Pittsburgh Steelers': 'PIT',
            'Minnesota Vikings': 'MIN',
            'New York Giants': 'NYG',
            'Detroit Lions': 'DET',
            'Los Angeles Rams': 'LAR',
            'Los Angeles Chargers': 'LAC',
            'San Francisco 49ers': 'SF',
            'Washington Commanders': 'WAS',
            'Tampa Bay Buccaneers': 'TB',
            'Dallas Cowboys': 'DAL',
            'Kansas City Chiefs': 'KC',
            'Seattle Seahawks': 'SEA',
            'Chicago Bears': 'CHI',
            'Cincinnati Bengals': 'CIN',
            'Atlanta Falcons': 'ATL',
            'Miami Dolphins': 'MIA',
            'Las Vegas Raiders': 'LV',
            'New York Jets': 'NYJ',
            'New England Patriots': 'NE',
            'Jacksonville Jaguars': 'JAC',
            'Cleveland Browns': 'CLE',
            'Indianapolis Colts': 'IND',
            'Arizona Cardinals': 'ARI',
            'Carolina Panthers': 'CAR',
            'New Orleans Saints': 'NO',
            'Tennessee Titans': 'TEN'
        }
        
        # If full name, convert to abbreviation
        if team in team_mapping:
            return team_mapping[team]
        
        # Already abbreviated
        return team
    
    def normalize_player_names(self, name: str) -> str:
        """
        Normalize player names for matching.
        
        - Remove extra whitespace
        - Handle suffixes (Jr., Sr., III, II, IV)
        - Standardize apostrophes and hyphens
        """
        if pd.isna(name):
            return None
        
        name = name.strip()
        
        # Remove leading/trailing quotes
        name = name.strip('"')
        
        # Normalize whitespace
        name = ' '.join(name.split())
        
        # Handle common suffixes (for matching)
        # We'll keep them but standardize
        suffixes = [' Jr.', ' Sr.', ' III', ' II', ' IV', ' V']
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip() + suffix
        
        return name
```

### 3. Transformation (`transformation.py`)

**Purpose**: Combine all data sources and calculate scoring variants

```python
class FantasyProsTransformer:
    """Transforms and merges FantasyPros data"""
    
    def __init__(self, cleaner: FantasyProsDataCleaner):
        self.cleaner = cleaner
    
    def merge_all_projections(
        self,
        qb_df: pd.DataFrame,
        flex_df: pd.DataFrame,
        k_df: pd.DataFrame,
        dst_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Combine all projection files into one DataFrame.
        
        Returns unified structure with all positions.
        """
        # Add position column to each
        qb_df['Position'] = 'QB'
        k_df['Position'] = 'K'
        dst_df['Position'] = 'DST'
        
        # Extract position from FLEX file
        flex_df['Position'] = flex_df['POS'].apply(self.cleaner.extract_base_position)
        flex_df['Position_Rank'] = flex_df['POS'].apply(self.cleaner.extract_position_rank)
        
        # Standardize column names for concatenation
        all_players = []
        
        # Process QBs
        for _, row in qb_df.iterrows():
            all_players.append({
                'Player': self.cleaner.normalize_player_names(row['Player']),
                'Team': self.cleaner.standardize_team_names(row['Team']),
                'Position': 'QB',
                'Pass_Att': row.get('Pass_Att', 0),
                'Pass_Cmp': row.get('Pass_Cmp', 0),
                'Pass_Yds': row.get('Pass_Yds', 0),
                'Pass_TD': row.get('Pass_TD', 0),
                'Pass_Int': row.get('Pass_Int', 0),
                'Rush_Att': row.get('Rush_Att', 0),
                'Rush_Yds': row.get('Rush_Yds', 0),
                'Rush_TD': row.get('Rush_TD', 0),
                'Rec': 0,
                'Rec_Yds': 0,
                'Rec_TD': 0,
                'FL': row.get('FL', 0),
                'FPTS': row.get('FPTS', 0),  # This is PPR
                'FG': 0,
                'FGA': 0,
                'XPT': 0
            })
        
        # Process FLEX (RB/WR/TE)
        for _, row in flex_df.iterrows():
            all_players.append({
                'Player': self.cleaner.normalize_player_names(row['Player']),
                'Team': self.cleaner.standardize_team_names(row['Team']),
                'Position': self.cleaner.extract_base_position(row['POS']),
                'Position_Rank': self.cleaner.extract_position_rank(row['POS']),
                'Pass_Att': 0,
                'Pass_Cmp': 0,
                'Pass_Yds': 0,
                'Pass_TD': 0,
                'Pass_Int': 0,
                'Rush_Att': row.get('Rush_Att', 0),
                'Rush_Yds': row.get('Rush_Yds', 0),
                'Rush_TD': row.get('Rush_TD', 0),
                'Rec': row.get('Rec', 0),
                'Rec_Yds': row.get('Rec_Yds', 0),
                'Rec_TD': row.get('Rec_TD', 0),
                'FL': row.get('FL', 0),
                'FPTS': row.get('FPTS', 0),  # This is PPR
                'FG': 0,
                'FGA': 0,
                'XPT': 0
            })
        
        # Process Kickers
        for _, row in k_df.iterrows():
            all_players.append({
                'Player': self.cleaner.normalize_player_names(row['Player']),
                'Team': self.cleaner.standardize_team_names(row['Team']),
                'Position': 'K',
                'Pass_Att': 0,
                'Pass_Cmp': 0,
                'Pass_Yds': 0,
                'Pass_TD': 0,
                'Pass_Int': 0,
                'Rush_Att': 0,
                'Rush_Yds': 0,
                'Rush_TD': 0,
                'Rec': 0,
                'Rec_Yds': 0,
                'Rec_TD': 0,
                'FL': 0,
                'FPTS': row.get('FPTS', 0),
                'FG': row.get('FG', 0),
                'FGA': row.get('FGA', 0),
                'XPT': row.get('XPT', 0)
            })
        
        # Process DST (Player is team name)
        for _, row in dst_df.iterrows():
            team_name = row['Player']
            all_players.append({
                'Player': team_name,
                'Team': self.cleaner.standardize_team_names(team_name),
                'Position': 'DST',
                'Pass_Att': 0,
                'Pass_Cmp': 0,
                'Pass_Yds': 0,
                'Pass_TD': 0,
                'Pass_Int': 0,
                'Rush_Att': 0,
                'Rush_Yds': 0,
                'Rush_TD': 0,
                'Rec': 0,
                'Rec_Yds': 0,
                'Rec_TD': 0,
                'FL': 0,
                'FPTS': row.get('FPTS', 0)
            })
        
        return pd.DataFrame(all_players)
    
    def calculate_scoring_variants(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate Standard and Half PPR from provided PPR projections.
        
        FPTS in the files appears to be PPR (full point per reception).
        We need to calculate:
        - Standard (0 PPR)
        - Half PPR (0.5 PPR)
        - Keep Full PPR as-is
        """
        # FPTS provided is Full PPR
        df['FPTS_FullPPR'] = df['FPTS']
        
        # Calculate Standard (remove reception points)
        df['FPTS_Standard'] = df['FPTS'] - df['Rec']
        
        # Calculate Half PPR (remove half reception points)
        df['FPTS_HalfPPR'] = df['FPTS'] - (df['Rec'] * 0.5)
        
        return df
    
    def merge_with_rankings(
        self,
        projections_df: pd.DataFrame,
        rankings_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Merge projections with rankings data.
        
        Adds: Overall rank, position rank, bye week, ADP
        """
        # Extract base position from rankings
        rankings_df['Base_Position'] = rankings_df['POS'].apply(
            self.cleaner.extract_base_position
        )
        rankings_df['Position_Rank'] = rankings_df['POS'].apply(
            self.cleaner.extract_position_rank
        )
        
        # Normalize names for matching
        rankings_df['Player_Normalized'] = rankings_df['PLAYER NAME'].apply(
            self.cleaner.normalize_player_names
        )
        projections_df['Player_Normalized'] = projections_df['Player'].apply(
            self.cleaner.normalize_player_names
        )
        
        # Merge
        merged = projections_df.merge(
            rankings_df[['Player_Normalized', 'RK', 'Base_Position', 
                        'Position_Rank', 'BYE WEEK', 'TIERS']],
            left_on=['Player_Normalized', 'Position'],
            right_on=['Player_Normalized', 'Base_Position'],
            how='left'
        )
        
        # Clean up
        merged = merged.rename(columns={
            'RK': 'Overall_Rank',
            'BYE WEEK': 'Bye_Week',
            'TIERS': 'Tier'
        })
        
        # For players not in rankings, assign high rank
        merged['Overall_Rank'] = merged['Overall_Rank'].fillna(999)
        
        return merged
    
    def generate_player_ids(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate unique player IDs.
        
        Format: {normalized_name}_{position}_{team}
        Example: jamarr_chase_wr_cin
        """
        def make_id(row):
            name = row['Player'].lower().replace("'", "").replace(".", "").replace(" ", "_")
            pos = row['Position'].lower()
            team = (row['Team'] or 'FA').lower()
            return f"{name}_{pos}_{team}"
        
        df['player_id'] = df.apply(make_id, axis=1)
        return df
```

### 4. VOR Calculation (`vor_calculation.py`)

```python
class VORCalculator:
    """Calculate Value Over Replacement for FantasyPros data"""
    
    # Baseline players based on 12-team league
    BASELINE_COUNTS = {
        "QB": 12,   # 1 per team
        "RB": 36,   # ~3 per team (2 starters + FLEX share)
        "WR": 36,   # ~3 per team (2 starters + FLEX share)
        "TE": 12,   # 1 per team
        "K": 12,    # 1 per team
        "DST": 12   # 1 per team
    }
    
    def calculate_baseline_vor(
        self,
        players_df: pd.DataFrame,
        league_size: int = 12
    ) -> pd.DataFrame:
        """
        Calculate baseline VOR for each player in each scoring format.
        
        Process for each position and scoring format:
        1. Sort players by projected points
        2. Find replacement player (e.g., RB36)
        3. Calculate VOR = Player Points - Replacement Points
        """
        scoring_formats = ['Standard', 'HalfPPR', 'FullPPR']
        
        for scoring in scoring_formats:
            fpts_col = f'FPTS_{scoring}'
            vor_col = f'VOR_{scoring}'
            
            # Calculate VOR for each position
            players_df[vor_col] = 0.0
            
            for position in self.BASELINE_COUNTS.keys():
                # Get players at this position
                pos_players = players_df[players_df['Position'] == position].copy()
                
                if len(pos_players) == 0:
                    continue
                
                # Sort by projected points
                pos_players = pos_players.sort_values(fpts_col, ascending=False)
                
                # Find replacement player
                replacement_idx = min(
                    self.BASELINE_COUNTS[position],
                    len(pos_players) - 1
                )
                replacement_points = pos_players.iloc[replacement_idx][fpts_col]
                
                # Calculate VOR for all players at position
                player_indices = pos_players.index
                players_df.loc[player_indices, vor_col] = (
                    pos_players[fpts_col] - replacement_points
                ).clip(lower=0)  # VOR can't be negative
        
        return players_df
```

### 5. Main Pipeline (`run_update.py`)

```python
def run_pipeline(year: int = 2025, data_dir: Optional[Path] = None) -> bool:
    """
    Run the complete FantasyPros data pipeline.
    
    Args:
        year: Season year (e.g., 2025)
        data_dir: Directory containing raw CSVs (default: data/raw/{year})
    
    Returns:
        True if successful
    """
    try:
        logger.info(f"Starting pipeline for {year} season...")
        
        # Set up directories
        if data_dir is None:
            data_dir = Path("data/raw") / str(year)
        
        output_dir = Path("data/processed")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Ingest all CSV files
        logger.info("Step 1: Ingesting CSV files...")
        ingester = FantasyProsIngester(data_dir, year)
        
        rankings_df = ingester.read_rankings()
        qb_df = ingester.read_qb_projections()
        flex_df = ingester.read_flex_projections()
        k_df = ingester.read_k_projections()
        dst_df = ingester.read_dst_projections()
        
        logger.info(f"Loaded: {len(rankings_df)} rankings, {len(qb_df)} QBs, "
                   f"{len(flex_df)} FLEX, {len(k_df)} Ks, {len(dst_df)} DSTs")
        
        # 2. Transform and merge
        logger.info("Step 2: Transforming and merging data...")
        cleaner = FantasyProsDataCleaner()
        transformer = FantasyProsTransformer(cleaner)
        
        # Merge all projections
        all_projections = transformer.merge_all_projections(qb_df, flex_df, k_df, dst_df)
        
        # Calculate scoring variants
        all_projections = transformer.calculate_scoring_variants(all_projections)
        
        # Merge with rankings
        final_df = transformer.merge_with_rankings(all_projections, rankings_df)
        
        # Generate player IDs
        final_df = transformer.generate_player_ids(final_df)
        
        logger.info(f"Merged data: {len(final_df)} total players")
        
        # 3. Calculate VOR
        logger.info("Step 3: Calculating VOR...")
        vor_calc = VORCalculator()
        final_df = vor_calc.calculate_baseline_vor(final_df, league_size=12)
        
        # 4. Convert to output format
        logger.info("Step 4: Generating output...")
        players_list = []
        
        for _, row in final_df.iterrows():
            player = {
                "player_id": row['player_id'],
                "name": row['Player'],
                "position": row['Position'],
                "team": row['Team'],
                "bye_week": int(row['Bye_Week']) if pd.notna(row['Bye_Week']) else None,
                "tier": int(row['Tier']) if pd.notna(row['Tier']) else None,
                "overall_rank": int(row['Overall_Rank']),
                "position_rank": int(row['Position_Rank']) if pd.notna(row['Position_Rank']) else None,
                
                # Stats
                "stats": {
                    "pass_att": float(row['Pass_Att']) if pd.notna(row['Pass_Att']) else 0,
                    "pass_cmp": float(row['Pass_Cmp']) if pd.notna(row['Pass_Cmp']) else 0,
                    "pass_yds": float(row['Pass_Yds']) if pd.notna(row['Pass_Yds']) else 0,
                    "pass_td": float(row['Pass_TD']) if pd.notna(row['Pass_TD']) else 0,
                    "pass_int": float(row['Pass_Int']) if pd.notna(row['Pass_Int']) else 0,
                    "rush_att": float(row['Rush_Att']) if pd.notna(row['Rush_Att']) else 0,
                    "rush_yds": float(row['Rush_Yds']) if pd.notna(row['Rush_Yds']) else 0,
                    "rush_td": float(row['Rush_TD']) if pd.notna(row['Rush_TD']) else 0,
                    "rec": float(row['Rec']) if pd.notna(row['Rec']) else 0,
                    "rec_yds": float(row['Rec_Yds']) if pd.notna(row['Rec_Yds']) else 0,
                    "rec_td": float(row['Rec_TD']) if pd.notna(row['Rec_TD']) else 0,
                    "fl": float(row['FL']) if pd.notna(row['FL']) else 0
                },
                
                # Projections (all 3 scoring formats)
                "projections": {
                    "standard": float(row['FPTS_Standard']),
                    "half_ppr": float(row['FPTS_HalfPPR']),
                    "full_ppr": float(row['FPTS_FullPPR'])
                },
                
                # VOR (all 3 scoring formats)
                "baseline_vor": {
                    "standard": float(row['VOR_Standard']),
                    "half_ppr": float(row['VOR_HalfPPR']),
                    "full_ppr": float(row['VOR_FullPPR'])
                }
            }
            
            players_list.append(player)
        
        # 5. Save output
        output_data = {
            "metadata": {
                "version": "1.0",
                "generated_at": datetime.now().isoformat(),
                "source": "FantasyPros",
                "season": year,
                "league_size": 12,
                "scoring_systems": ["standard", "half_ppr", "full_ppr"],
                "total_players": len(players_list)
            },
            "players": players_list
        }
        
        output_file = output_dir / f"players_{year}.json"
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        # Update latest symlink
        latest_link = output_dir / "players_latest.json"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(output_file.name)
        
        logger.info(f"✓ Pipeline complete! Output: {output_file}")
        logger.info(f"  Total players: {len(players_list)}")
        logger.info(f"  By position: QB={len([p for p in players_list if p['position']=='QB'])}, "
                   f"RB={len([p for p in players_list if p['position']=='RB'])}, "
                   f"WR={len([p for p in players_list if p['position']=='WR'])}, "
                   f"TE={len([p for p in players_list if p['position']=='TE'])}")
        
        return True
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    import sys
    
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    data_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    
    success = run_pipeline(year, data_dir)
    sys.exit(0 if success else 1)
```

## Usage

```bash
# Process 2025 season data
python -m src.data_pipeline.run_update 2025

# With custom directory
python -m src.data_pipeline.run_update 2025 /path/to/csvs

# Output will be: data/processed/players_2025.json
```

## Output Format

```json
{
  "metadata": {
    "version": "1.0",
    "generated_at": "2025-02-07T10:00:00",
    "source": "FantasyPros",
    "season": 2025,
    "league_size": 12,
    "scoring_systems": ["standard", "half_ppr", "full_ppr"],
    "total_players": 650
  },
  "players": [
    {
      "player_id": "jamarr_chase_wr_cin",
      "name": "Ja'Marr Chase",
      "position": "WR",
      "team": "CIN",
      "bye_week": 10,
      "tier": 1,
      "overall_rank": 1,
      "position_rank": 1,
      "stats": {
        "rush_att": 1.6,
        "rush_yds": 12.7,
        "rush_td": 0.0,
        "rec": 120.1,
        "rec_yds": 1580.9,
        "rec_td": 12.2,
        "fl": 0.6
      },
      "projections": {
        "standard": 111.6,
        "half_ppr": 171.7,
        "full_ppr": 231.7
      },
      "baseline_vor": {
        "standard": 45.2,
        "half_ppr": 89.3,
        "full_ppr": 133.4
      }
    }
  ]
}
```

## Testing

```python
# Milestone 1: CSV Ingestion
def test_ingestion():
    ingester = FantasyProsIngester(Path("data/raw/2025"), 2025)
    
    rankings = ingester.read_rankings()
    assert len(rankings) > 500
    assert "PLAYER NAME" in rankings.columns
    
    qb = ingester.read_qb_projections()
    assert "Pass_Att" in qb.columns  # Not duplicate
    assert "Rush_Att" in qb.columns
    
    print("✓ Ingestion works!")

# Milestone 2: Cleaning
def test_cleaning():
    cleaner = FantasyProsDataCleaner()
    
    assert cleaner.extract_base_position("WR1") == "WR"
    assert cleaner.extract_base_position("RB23") == "RB"
    assert cleaner.extract_position_rank("WR1") == 1
    assert cleaner.extract_position_rank("RB23") == 23
    
    assert cleaner.standardize_team_names("Philadelphia Eagles") == "PHI"
    assert cleaner.standardize_team_names("PHI") == "PHI"
    
    print("✓ Cleaning works!")

# Milestone 3: Full Pipeline
def test_full_pipeline():
    success = run_pipeline(2025, Path("data/raw/2025"))
    assert success
    
    # Verify output
    with open("data/processed/players_2025.json") as f:
        data = json.load(f)
    
    assert len(data["players"]) > 500
    assert data["players"][0]["baseline_vor"]["half_ppr"] > 0
    
    print(f"✓ Pipeline complete: {len(data['players'])} players processed")
```

---

## Document Version
- **Version**: 2.0 (Updated for real FantasyPros data)
- **Last Updated**: 2025-02-07
- **Status**: Ready for Implementation
