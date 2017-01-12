import openpathsampling as paths

class NoEngine(paths.engines.DynamicsEngine):
    pass

class ShootingStub(paths.pathmover.PathMover):
    """Stub to mimic a shooting move.

    Parameters
    ----------
    ensemble : paths.Ensemble
        the ensemble for the shooting mover
    selector : paths.ShootingPointSelector or None
        the selector for the shooting point. Default None creates a
        UniformSelector. Currently, only UniformSelector is supported.
    engine : paths.engines.DynamicsEngine
        the engine to report as the source of the dynamics
    pre_joined : bool
        whether the input trial trajectories are pre-joined into complete
        trajectories, or take partial one-way segments which should by
        dynamically joined. Currently defaults to pre_joined=True (likely to
        change soon, though).

    Attributes
    ----------
    mimic : paths.OneWayShootingMover
        the mover that this stub mimics

    """
    def __init__(self, ensemble, selector=None, engine=None, pre_joined=True):
        super(ShootingStub, self).__init__()
        if engine is None:
            engine = NoEngine()
        if selector is None:
            selector = paths.UniformSelector()  # default
        self.engine = engine
        self.selector = selector
        self.ensemble = ensemble
        self.pre_joined = pre_joined
        self.mimic = paths.OneWayShootingMover(ensemble, selector, engine)

    @staticmethod
    def join_one_way(input_trajectory, partial_trial, shooting_point,
                     direction):
        """Create a one-way trial trajectory

        Parameters
        ----------
        input_trajectory : paths.Trajectory
            the previous complete trajectory
        partial_trial : paths.Trajectory
            The partial (one-way) trial trajectory. Must *not* include the
            shooting point.
        shooting_point : paths.Snapshot
            the snapshot for the shooting point -- must be a member of the
            input trajectory
        direction : +1 or -1
            if positive, treat as forward shooting; if negative, treat as
            backward shooting

        Returns
        -------
        paths.Trajectory
            the complete trial trajectory
        """
        shooting_idx = input_trajectory.index(shooting_point)
        if direction > 0:
            joined_trajectory = (input_trajectory[:shooting_idx+1] +
                                 partial_trial)
        elif direction < 0:
            joined_trajectory = (partial_trial +
                                 input_trajectory[shooting_idx:])
        else: # pragma: no cover
            raise RuntimeError("Bad direction for shooting: " +
                               str(direction))
        return joined_trajectory


    def move(self, input_sample, trial_trajectory, shooting_point, accepted,
             direction=None):
        """Fake a move.

        Parameters
        ----------
        input_sample: :class:`paths.Sample`
            the input sample for this shooting move
        trial_trajectory: :class:`paths.Trajectory`
            the trial trajectory generated by this move
        shooting_point: :class:`paths.Snapshot`
            the shooting point snapshot for this trial
        accepted: bool
            whether the trial was accepted
        direction: +1, -1, or None
            direction of the shooting move (positive is forward, negative is
            backward). If self.pre_joined is True, the trial trajectory is
            reconstructed from the parts. To use the exact input trial
            trajectory with self.pre_joined == True, set direction=None
        """
        initial_trajectory = input_sample.trajectory
        replica = input_sample.replica
        ensemble = input_sample.ensemble

        if not self.pre_joined:
            trial_trajectory = self.join_one_way(initial_trajectory,
                                                 trial_trajectory,
                                                 shooting_point,
                                                 direction)

        # determine the direction based on trial trajectory
        shared = trial_trajectory.shared_subtrajectory(initial_trajectory)
        if len(shared) == 0:
            raise RuntimeError("No shared frames. "
                               + "Were these shot from each other?")

        if shared[0] == trial_trajectory[0]:
            choice = 0  # forward submover
        elif shared[-1] == trial_trajectory[-1]:
            choice = 1  # backward submover
        else:  # pragma: no cover
            raise RuntimeError("Are you sure this is 1-way shooting?")

        details = paths.Details(
            initial_trajectory=initial_trajectory,
            shooting_snapshot=shooting_point
        )

        trial = paths.Sample(
            replica=replica,
            trajectory=trial_trajectory,
            ensemble=ensemble,
            parent=input_sample,
            # details=trial_details,
            mover=self.mimic.movers[choice]
        )

        trials = [trial]
        # move_details = paths.MoveDetails()

        if accepted:
            inner = paths.AcceptedSampleMoveChange(
                samples=trials,
                mover=self.mimic.movers[choice],
                details=details
            )
        else:
            inner = paths.RejectedSampleMoveChange(
                samples=trial,
                mover=self.mimic.movers[choice],
                details=details
            )

        rc_details = paths.MoveDetails()
        rc_details.inputs = []
        rc_details.choice = choice
        rc_details.chosen_mover = self.mimic.movers[choice]
        rc_details.probability = 0.5
        rc_details.weights = [1, 1]

        return paths.RandomChoiceMoveChange(
            subchange=inner,
            mover=self.mimic,
            details=rc_details
        )
